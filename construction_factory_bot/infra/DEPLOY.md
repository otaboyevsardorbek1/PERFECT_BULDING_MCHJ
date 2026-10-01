# 🚀 Production Deploy — Qurilish Korxonasi

## 📋 Mundarija

1. [Texnik talablar](#1-texnik-talablar)
2. [Bosqich 1: Infratuzilma (Terraform)](#2-bosqich-1-infratuzilma-terraform)
3. [Bosqich 2: Kubernetes klaster](#3-bosqich-2-kubernetes-klaster)
4. [Bosqich 3: Istio Service Mesh](#4-bosqich-3-istio-service-mesh)
5. [Bosqich 4: Database (PostgreSQL)](#5-bosqich-4-database-postgresql)
6. [Bosqich 5: Docker image'lar](#6-bosqich-5-docker-image-lar)
7. [Bosqich 6: Kubernetes resurslari](#7-bosqich-6-kubernetes-resurslari)
8. [Bosqich 7: Monitoring & Observability](#8-bosqich-7-monitoring--observability)
9. [Bosqich 8: CI/CD (GitHub Actions)](#9-bosqich-8-cicd-github-actions)
10. [Bosqich 9: GitOps (ArgoCD)](#10-bosqich-9-gitops-argocd)
11. [Xavfsizlik cheklisti](#11-xavfsizlik-cheklisti)
12. [Tekshiruvlar](#12-tekshiruvlar)

---

## 1. Texnik talablar

### Kerakli vositalar
```bash
# CLI vositalar
aws --version          # AWS CLI v2
terraform --version    # Terraform >= 1.5
kubectl version        # kubectl >= 1.28
istioctl version       # Istio >= 1.20
helm version           # Helm >= 3.13
docker --version       # Docker >= 24
argocd version         # ArgoCD CLI >= 2.9
```

### Min. resurslar (AWS)
| Resurs | Miqdor | Narxi (oylik) |
|---|---|---|
| EKS Cluster | 3 node (t3.large) | ~$300 |
| RDS PostgreSQL | db.t3.medium, Multi-AZ | ~$200 |
| S3 Bucket | Cross-region backup | ~$10 |
| ElastiCache Redis | cache.t3.micro | ~$30 |
| **Jami** | | **~$540/oy** |

---

## 2. Bosqich 1: Infratuzilma (Terraform)

### AWS VPC + EKS
```bash
cd infra/terraform

# Terraform init
terraform init

# Plan
terraform plan -var-file="prod.tfvars"

# Apply
terraform apply -var-file="prod.tfvars"
```

### Terraform konfiguratsiyasi
```hcl
# infra/terraform/main.tf
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "qurilish-prod"
  cluster_version = "1.28"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    general = {
      desired_size = 3
      min_size     = 2
      max_size     = 10

      instance_types = ["t3.large"]
      capacity_type  = "ON_DEMAND"
    }
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "qurilish-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = false
  enable_dns_hostnames = true
}
```

---

## 3. Bosqich 2: Kubernetes klaster

### Kubectl sozlash
```bash
aws eks update-kubeconfig --name qurilish-prod --region ap-south-1

# Tekshirish
kubectl cluster-info
kubectl get nodes
```

### Namespace yaratish
```bash
kubectl apply -f infra/k8s/namespace.yaml
```

---

## 4. Bosqich 3: Istio Service Mesh

### Istio o'rnatish
```bash
# Istio'ni yuklab olish
istioctl install --set profile=default -y

# Namespace'ga Istio inject
kubectl label namespace qurilish-prod istio-injection=enabled

# Tekshirish
istioctl verify-install
kubectl get pods -n istio-system
```

### Istio konfiguratsiyalarni qo'llash
```bash
# VirtualService + DestinationRule
kubectl apply -f infra/istio/virtual-service.yaml

# mTLS + AuthorizationPolicy + Rate Limiting
kubectl apply -f infra/istio/security.yaml
```

### Istio Dashboard (Kiali)
```bash
# Kiali o'rnatish (monitoring uchun)
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/kiali.yaml

# Kiali'ga kirish
istioctl dashboard kiali
```

---

## 5. Bosqich 4: Database (PostgreSQL)

### AWS RDS yaratish
```bash
aws rds create-db-instance \
  --db-instance-identifier qurilish-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.4 \
  --master-username qurilish_admin \
  --master-user-password $(openssl rand -base64 32) \
  --allocated-storage 50 \
  --max-allocated-storage 200 \
  --storage-type gp3 \
  --storage-encrypted \
  --multi-az \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "sun:05:00-sun:06:00" \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name qurilish-subnet \
  --no-publicly-accessible \
  --tags Key=Environment,Value=production
```

### Kubernetes Secrets yaratish
```bash
# DB credentials
kubectl create secret generic qurilish-db-credentials \
  --from-literal=host=qurilish-db.xxxxx.ap-south-1.rds.amazonaws.com \
  --from-literal=database=qurilish_factory \
  --from-literal=username=qurilish_admin \
  --from-literal=password=$(aws rds generate-db-auth-token ...) \
  -n qurilish-prod

# API secrets
kubectl create secret generic qurilish-api-secrets \
  --from-literal=secret-key=$(openssl rand -base64 64) \
  -n qurilish-prod

# Bot secrets
kubectl create secret generic qurilish-bot-secrets \
  --from-literal=bot-token=YOUR_BOT_TOKEN \
  --from-literal=admin-ids=YOUR_ADMIN_ID \
  -n qurilish-prod

# Backup secrets
kubectl create secret generic qurilish-backup-secrets \
  --from-literal=encryption-password=$(openssl rand -base64 32) \
  -n qurilish-prod
```

---

## 6. Bosqich 5: Docker image'lar

### Image'larni build qilish
```bash
# Login to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.ap-south-1.amazonaws.com

REPO=123456789.dkr.ecr.ap-south-1.amazonaws.com/qurilish

# API image
docker build -t $REPO/api:latest -f Dockerfile .
docker push $REPO/api:latest

# Web image (xuddi shu Dockerfile, faqat command farqi)
docker build -t $REPO/web:latest .
docker push $REPO/web:latest

# Bot image
docker build -t $REPO/bot:latest .
docker push $REPO/bot:latest
```

---

## 7. Bosqich 6: Kubernetes resurslari

### Barcha resurslarni qo'llash
```bash
# PVC (database va backup uchun)
kubectl apply -f infra/k8s/pvc.yaml

# API deployment
kubectl apply -f infra/k8s/api-deployment.yaml

# Web deployment
kubectl apply -f infra/k8s/web-deployment.yaml

# Bot deployment
kubectl apply -f infra/k8s/bot-deployment.yaml

# Tekshirish
kubectl get pods -n qurilish-prod
kubectl get svc -n qurilish-prod
kubectl get hpa -n qurilish-prod
```

### Ingress yaratish
```yaml
# infra/k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: qurilish-ingress
  namespace: qurilish-prod
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - app.qurilish-factory.uz
    - api.qurilish-factory.uz
    secretName: qurilish-tls
  rules:
  - host: app.qurilish-factory.uz
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: qurilish-web
            port:
              number: 80
  - host: api.qurilish-factory.uz
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: qurilish-api
            port:
              number: 8000
```

---

## 8. Bosqich 7: Monitoring & Observability

### Prometheus + Grafana
```bash
# Prometheus
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/prometheus.yaml

# Grafana
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/grafana.yaml

# Jaeger (distributed tracing)
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.20/samples/addons/jaeger.yaml

# Loki (log aggregation)
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack -n monitoring --create-namespace
```

### Alertmanager (Slack/Telegram)
```yaml
# infra/monitoring/alertmanager-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
  namespace: monitoring
data:
  alertmanager.yml: |
    global:
      resolve_timeout: 5m
    route:
      receiver: 'slack-notifications'
      group_by: ['alertname', 'cluster', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
    receivers:
    - name: 'slack-notifications'
      slack_configs:
      - channel: '#qurilish-alerts'
        send_resolved: true
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.description }}'
```

---

## 9. Bosqich 8: CI/CD (GitHub Actions)

### `.github/workflows/deploy.yml`
```yaml
name: Production Deploy

on:
  push:
    branches: [main]

env:
  AWS_REGION: ap-south-1
  ECR_REPOSITORY: qurilish
  EKS_CLUSTER: qurilish-prod

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.13'
    
    - name: Install dependencies
      run: |
        cd construction_factory_bot
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        cd construction_factory_bot
        pytest tests/ -v --tb=short

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Login to ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v2
    
    - name: Build and push API
      run: |
        cd construction_factory_bot
        docker build -t ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}/api:${{ github.sha }} .
        docker push ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}/api:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
    - name: Deploy to EKS
      run: |
        aws eks update-kubeconfig --name ${{ env.EKS_CLUSTER }} --region ${{ env.AWS_REGION }}
        
        # Image yangilash
        kubectl set image deployment/qurilish-api \
          api=${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}/api:${{ github.sha }} \
          -n qurilish-prod
        
        # Rollout kutish
        kubectl rollout status deployment/qurilish-api -n qurilish-prod --timeout=300s
```

---

## 10. Bosqich 9: GitOps (ArgoCD)

### ArgoCD Application
```yaml
# infra/argocd/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: qurilish-factory
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/qurilish-factory.git
    targetRevision: main
    path: construction_factory_bot/infra/k8s
  destination:
    server: https://kubernetes.default.svc
    namespace: qurilish-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### ArgoCD o'rnatish
```bash
# ArgoCD namespace
kubectl create namespace argocd

# ArgoCD o'rnatish
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Initial password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# ArgoCD dashboard
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

---

## 11. Xavfsizlik cheklisti

### ✅ Tekshirish keraklar
- [ ] Secrets (DB, API, Bot) — Kubernetes Secrets yoki AWS Secrets Manager
- [ ] mTLS — Istio STRICT mode yoqilgan
- [ ] NetworkPolicy — faqat kerakli portlar ochiq
- [ ] RBAC — xodimlar faqat o'z rollariga mos resurslarni ko'radi
- [ ] OPA/Gatekeeper — Kubernetes policy enforcement
- [ ] Audit log — barcha API so'rovlari loglanadi
- [ ] SSL/TLS — Let's Encrypt yoki AWS Certificate Manager
- [ ] WAF — AWS WAF yoki Cloudflare
- [ ] Backup — avtomatik kunlik backup (Velero + S3)
- [ ] DR — cross-region replication

---

## 12. Tekshiruvlar

### Deploy dan keyin
```bash
# 1. Pod'lar sog'ligi
kubectl get pods -n qurilish-prod

# 2. API healthcheck
kubectl exec -n qurilish-prod deploy/qurilish-api -- \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read())"

# 3. Istio status
istioctl analyze -n qurilish-prod

# 4. HPA holati
kubectl get hpa -n qurilish-prod

# 5. Logs
kubectl logs -n qurilish-prod deploy/qurilish-api --tail=50

# 6. Chaos test
bash infra/chaos/run-chaos.sh slo-check
```

### Rollback (kerak bo'lsa)
```bash
# Deployment rollback
kubectl rollout undo deployment/qurilish-api -n qurilish-prod

# ArgoCD rollback
argocd app rollback qurilish-factory
```

---

## 📞 Qo'llanma

Savollar bo'lsa:
- Telegram: @qurilish_support
- Email: dev@qurilish-factory.uz
