#!/bin/bash
# ============================================================
# 🚀 Production Deploy — Qurilish Korxonasi
# ============================================================
# Ishlatish:
#   ./deploy.sh [bosqich]
#
# Misollar:
#   ./deploy.sh all          # Barcha bosqichlar
#   ./deploy.sh build        # Faqat Docker build
#   ./deploy.sh helm         # Faqat Helm deploy
#   ./deploy.sh status       # Holatni tekshirish
#   ./deploy.sh rollback     # Orqaga qaytarish

set -euo pipefail

# =============== SOZLAMALAR ===============
NAMESPACE="qurilish-prod"
HELM_RELEASE="qurilish-factory"
HELM_CHART="./infra/helm/qurilish-factory"
AWS_REGION="ap-south-1"
ECR_REPO="123456789.dkr.ecr.ap-south-1.amazonaws.com/qurilish"
EKS_CLUSTER="qurilish-prod"
IMAGE_TAG="${1:-latest}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $1"; }
fail() { echo -e "${RED}[$(date +%H:%M:%S)] FAIL:${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[$(date +%H:%M:%S)] INFO:${NC} $1"; }

# =============== BOSQICH 1: INFRATUZILMA ===============
deploy_infra() {
    log "🏗️  Bosqich 1: Infratuzilma (Terraform)..."
    
    cd infra/terraform
    
    if [ ! -f "terraform.tfstate" ]; then
        log "Terraform init..."
        terraform init
    fi
    
    log "Terraform plan..."
    terraform plan -var-file="prod.tfvars" -out=tfplan
    
    log "Terraform apply..."
    terraform apply tfplan
    
    cd ../..
    
    log "✅ Infratuzilma deploy qilindi"
}

# =============== BOSQICH 2: KUBERNETES KLASTER ===============
setup_kubectl() {
    log "☸️  Bosqich 2: Kubernetes klaster..."
    
    aws eks update-kubeconfig --name $EKS_CLUSTER --region $AWS_REGION
    
    kubectl cluster-info
    kubectl get nodes
    
    log "✅ Kubernetes klaster tayyor"
}

# =============== BOSQICH 3: ISTIO ===============
deploy_istio() {
    log "🕸️  Bosqich 3: Istio Service Mesh..."
    
    # Istio o'rnatish (agar yo'q bo'lsa)
    if ! istioctl verify-install --quiet 2>/dev/null; then
        log "Istio o'rnatilmoqda..."
        istioctl install --set profile=default -y
    fi
    
    # Namespace label
    kubectl label namespace $NAMESPACE istio-injection=enabled --overwrite
    
    # Istio konfiguratsiyalar
    kubectl apply -f infra/istio/virtual-service.yaml
    kubectl apply -f infra/istio/security.yaml
    
    # Tekshirish
    istioctl analyze -n $NAMESPACE
    
    log "✅ Istio konfiguratsiyalari qo'llanildi"
}

# =============== BOSQICH 4: DOCKER BUILD ===============
build_images() {
    log "🐳 Bosqich 4: Docker image'lar build..."
    
    # ECR login
    aws ecr get-login-password --region $AWS_REGION | \
        docker login --username AWS --password-stdin $ECR_REPO
    
    # API image
    log "API image build..."
    docker build -t $ECR_REPO/api:$IMAGE_TAG .
    docker push $ECR_REPO/api:$IMAGE_TAG
    
    # Web image
    log "Web image build..."
    docker build -t $ECR_REPO/web:$IMAGE_TAG .
    docker push $ECR_REPO/web:$IMAGE_TAG
    
    # Bot image
    log "Bot image build..."
    docker build -t $ECR_REPO/bot:$IMAGE_TAG .
    docker push $ECR_REPO/bot:$IMAGE_TAG
    
    log "✅ Docker image'lar yuklandi"
}

# =============== BOSQICH 5: SECRETS ===============
create_secrets() {
    log "🔐 Bosqich 5: Kubernetes Secrets..."
    
    # DB credentials
    if ! kubectl get secret qurilish-db-credentials -n $NAMESPACE &>/dev/null; then
        kubectl create secret generic qurilish-db-credentials \
            --from-literal=host=${DB_HOST:-localhost} \
            --from-literal=database=${DB_NAME:-qurilish_factory} \
            --from-literal=username=${DB_USER:-qurilish_admin} \
            --from-literal=password=${DB_PASSWORD:-changeme} \
            -n $NAMESPACE
    fi
    
    # API secrets
    if ! kubectl get secret qurilish-api-secrets -n $NAMESPACE &>/dev/null; then
        kubectl create secret generic qurilish-api-secrets \
            --from-literal=secret-key=$(openssl rand -base64 64) \
            -n $NAMESPACE
    fi
    
    # Bot secrets
    if ! kubectl get secret qurilish-bot-secrets -n $NAMESPACE &>/dev/null; then
        kubectl create secret generic qurilish-bot-secrets \
            --from-literal=bot-token=${BOT_TOKEN:-changeme} \
            --from-literal=admin-ids=${ADMIN_IDS:-123456789} \
            -n $NAMESPACE
    fi
    
    # Backup secrets
    if ! kubectl get secret qurilish-backup-secrets -n $NAMESPACE &>/dev/null; then
        kubectl create secret generic qurilish-backup-secrets \
            --from-literal=encryption-password=$(openssl rand -base64 32) \
            -n $NAMESPACE
    fi
    
    log "✅ Secrets yaratildi"
}

# =============== BOSQICH 6: HELM DEPLOY ===============
deploy_helm() {
    log "📦 Bosqich 6: Helm deploy..."
    
    # Namespace yaratish
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    
    # Helm upgrade/install
    helm upgrade --install $HELM_RELEASE $HELM_CHART \
        --namespace $NAMESPACE \
        --set global.imageTag=$IMAGE_TAG \
        --set global.imageRegistry=$ECR_REPO \
        --wait \
        --timeout 10m
    
    # Tekshirish
    kubectl get pods -n $NAMESPACE
    kubectl get svc -n $NAMESPACE
    kubectl get ingress -n $NAMESPACE
    
    log "✅ Helm deploy tugadi"
}

# =============== BOSQICH 7: TEKSHIRISH ===============
verify_deploy() {
    log "🔍 Bosqich 7: Deploy tekshirish..."
    
    # Pod'lar holati
    log "Pod'lar:"
    kubectl get pods -n $NAMESPACE -o wide
    
    # API healthcheck
    log "API healthcheck..."
    kubectl exec -n $NAMESPACE deploy/${HELM_RELEASE}-api -- \
        python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health'); print(r.read().decode())" 2>/dev/null || \
        warn "API healthcheck ishlamadi (pod'lar hali tayyor bo'lishi mumkin)"
    
    # Istio status
    log "Istio status:"
    istioctl analyze -n $NAMESPACE
    
    # HPA holati
    log "HPA:"
    kubectl get hpa -n $NAMESPACE
    
    # Logs (oxirgi 10 qator)
    log "API logs (oxirgi 10 qator):"
    kubectl logs -n $NAMESPACE deploy/${HELM_RELEASE}-api --tail=10 2>/dev/null || true
    
    log "✅ Deploy tekshirildi"
}

# =============== ROLLBACK ===============
rollback() {
    log "⏪ Rollback..."
    
    helm rollback $HELM_RELEASE -n $NAMESPACE
    
    kubectl rollout status deployment/${HELM_RELEASE}-api -n $NAMESPACE --timeout=300s
    
    log "✅ Rollback tugadi"
}

# =============== STATUS ===============
status() {
    log "📊 Tizim holati:"
    
    echo ""
    echo "=== Pods ==="
    kubectl get pods -n $NAMESPACE -o wide
    
    echo ""
    echo "=== Services ==="
    kubectl get svc -n $NAMESPACE
    
    echo ""
    echo "=== Ingress ==="
    kubectl get ingress -n $NAMESPACE
    
    echo ""
    echo "=== HPA ==="
    kubectl get hpa -n $NAMESPACE
    
    echo ""
    echo "=== PVC ==="
    kubectl get pvc -n $NAMESPACE
    
    echo ""
    echo "=== Events (oxirgi 10) ==="
    kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10
    
    echo ""
    echo "=== Helm releases ==="
    helm list -n $NAMESPACE
}

# =============== ASOSIY TANLOV ===============
case "${1:-all}" in
    infra)
        deploy_infra
        ;;
    kubectl|k8s)
        setup_kubectl
        ;;
    istio)
        deploy_istio
        ;;
    build)
        build_images
        ;;
    secrets)
        create_secrets
        ;;
    helm)
        deploy_helm
        ;;
    verify|check)
        verify_deploy
        ;;
    rollback)
        rollback
        ;;
    status)
        status
        ;;
    all)
        log "🚀 TO'LIQ DEPLOY boshlandi..."
        echo ""
        
        log "1/7 Infratuzilma..."
        # deploy_infra  # Faqat birinchi marta
        
        log "2/7 Kubernetes..."
        setup_kubectl
        
        log "3/7 Istio..."
        deploy_istio
        
        log "4/7 Docker build..."
        build_images
        
        log "5/7 Secrets..."
        create_secrets
        
        log "6/7 Helm deploy..."
        deploy_helm
        
        log "7/7 Tekshirish..."
        verify_deploy
        
        echo ""
        log "🎉 DEPLOY MUVAFFAQIYATLI TUGADI!"
        echo ""
        info "🌐 Web: https://app.qurilish-factory.uz"
        info "🔌 API: https://api.qurilish-factory.uz"
        info "📊 ArgoCD: kubectl port-forward svc/argocd-server -n argocd 8080:443"
        info "📊 Kiali: istioctl dashboard kiali"
        info "📊 Grafana: istioctl dashboard grafana"
        ;;
    *)
        echo "Ishlatish: $0 [all|infra|kubectl|istio|build|secrets|helm|verify|rollback|status]"
        exit 1
        ;;
esac

log "🏁 Deploy tugadi!"
