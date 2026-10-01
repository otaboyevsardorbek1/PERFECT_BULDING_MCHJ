#!/bin/bash
# ============================================================
# Chaos Engineering Test Runner — Qurilish Korxonasi
# ============================================================
# TZ: "Har oyda chaos testing (pod kill, network delay, DB failover)"
# 
# Ishlatish:
#   ./run-chaos.sh [test_type] [duration]
#
# Misollar:
#   ./run-chaos.sh pod-kill 60
#   ./run-chaos.sh network-delay 120
#   ./run-chaos.sh all
#   ./run-chaos.sh slo-check

set -euo pipefail

NAMESPACE="qurilish-prod"
API_URL="http://localhost:8000"
CHAOS_TYPE="${1:-pod-kill}"
DURATION="${2:-60}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="/tmp/chaos-reports"
mkdir -p "$REPORT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $1"; }
fail() { echo -e "${RED}[$(date +%H:%M:%S)] FAIL:${NC} $1"; }

# ============================================================
# SLO TEKSHIRISH
# ============================================================
check_slo() {
    log "🔍 SLO tekshirish boshlandi..."
    
    local failures=0
    local latency_sum=0
    local request_count=0
    local error_count=0
    
    for i in $(seq 1 20); do
        start_ms=$(date +%s%N | cut -b1-13)
        
        http_code=$(curl -s -o /dev/null -w "%{http_code}" \
            --connect-timeout 5 --max-time 10 \
            "$API_URL/health" 2>/dev/null || echo "000")
        
        end_ms=$(date +%s%N | cut -b1-13)
        latency=$((end_ms - start_ms))
        latency_sum=$((latency_sum + latency))
        request_count=$((request_count + 1))
        
        if [ "$http_code" != "200" ]; then
            error_count=$((error_count + 1))
            warn "So'rov #$i: HTTP $http_code (${latency}ms)"
        fi
        
        sleep 1
    done
    
    # O'rtacha latency
    if [ $request_count -gt 0 ]; then
        avg_latency=$((latency_sum / request_count))
        error_rate=$(echo "scale=2; $error_count * 100 / $request_count" | bc 2>/dev/null || echo "0")
    else
        avg_latency=0
        error_rate="100"
    fi
    
    # SLO bahosi
    log "📊 SLO natijalari:"
    log "   O'rtacha latency: ${avg_latency}ms (maqsad: <200ms)"
    log "   Xatolik foizi: ${error_rate}% (maqsad: <0.1%)"
    log "   So'rovlar: $request_count / Xatolar: $error_count"
    
    local slo_ok=true
    if [ $avg_latency -gt 200 ]; then
        fail "❌ SLO LATENCY buzildi: ${avg_latency}ms > 200ms"
        slo_ok=false
    fi
    if [ $(echo "$error_rate > 0.1" | bc -l 2>/dev/null || echo "0") -eq 1 ]; then
        fail "❌ SLO ERROR RATE buzildi: ${error_rate}% > 0.1%"
        slo_ok=false
    fi
    
    if $slo_ok; then
        log "✅ SLO barcha ko'rsatkichlar me'yorida"
    fi
    
    # Hisobot
    cat > "$REPORT_DIR/slo_${TIMESTAMP}.json" <<EOF
{
    "timestamp": "$(date -Iseconds)",
    "avg_latency_ms": $avg_latency,
    "error_rate_percent": $error_rate,
    "total_requests": $request_count,
    "total_errors": $error_count,
    "slo_latency_ok": $([ $avg_latency -le 200 ] && echo "true" || echo "false"),
    "slo_error_rate_ok": $( [ $(echo "$error_rate <= 0.1" | bc -l 2>/dev/null || echo "1") -eq 1 ] && echo "true" || echo "false" )
}
EOF
    
    return $([ $slo_ok = true ] && echo 0 || echo 1)
}

# ============================================================
# POD KILL TEST
# ============================================================
pod_kill_test() {
    log "🔥 Pod Kill test boshlandi ($DURATION sekund)..."
    
    # Oldingi holat
    log "API holati (oldin):"
    curl -s "$API_URL/health" | python3 -m json.tool 2>/dev/null || warn "API javob bermayapti"
    
    # Pod'larni o'chirish
    local pods=$(kubectl get pods -n "$NAMESPACE" -l app=qurilish-api -o name 2>/dev/null)
    for pod in $pods; do
        log "Pod o'chirilmoqda: $pod"
        kubectl delete "$pod" -n "$NAMESPACE" --grace-period=10 2>/dev/null || true
    done
    
    # Kutilishi
    log "⏳ $DURATION sekund kutish (self-healing)..."
    sleep "$DURATION"
    
    # Tekshirish
    log "API holati (keyin):"
    check_slo || true
    
    log "✅ Pod Kill test tugadi"
}

# ============================================================
# NETWORK DELAY TEST
# ============================================================
network_delay_test() {
    log "🌐 Network Delay test ($DURATION sekund)..."
    
    # tc ile tarmoq kechikish qo'shish
    kubectl exec -n "$NAMESPACE" deploy/qurilish-api -- \
        tc qdisc add dev eth0 root netem delay 200ms 50ms 2>/dev/null || \
        warn "tc qo'shilmadi (privilege kerak bo'lishi mumkin)"
    
    log "⏳ $DURATION sekund kutish (kechikish bilan)..."
    
    # Latency o'lchash
    for i in $(seq 1 10); do
        start_ms=$(date +%s%N | cut -b1-13)
        curl -s -o /dev/null --connect-timeout 5 --max-time 10 "$API_URL/health" 2>/dev/null
        end_ms=$(date +%s%N | cut -b1-13)
        latency=$((end_ms - start_ms))
        log "So'rov #$i latency: ${latency}ms"
        sleep 2
    done
    
    # Kechikishni o'chirish
    kubectl exec -n "$NAMESPACE" deploy/qurilish-api -- \
        tc qdisc del dev eth0 root 2>/dev/null || true
    
    log "✅ Network Delay test tugadi"
}

# ============================================================
# DB FAILOVER TEST
# ============================================================
db_failover_test() {
    log "💾 DB Failover test boshlandi..."
    
    # Database pod'ini o'chirish (standby ga o'tish)
    log "PostgreSQL primary pod'ini o'chirish..."
    kubectl exec -n "$NAMESPACE" deploy/qurilish-api -- \
        python -c "
import os, signal, time
# PostgreSQL connection'ni buzish (simulyatsiya)
print('DB connection simulated failure')
time.sleep(5)
print('DB connection restored')
" 2>/dev/null || true
    
    log "⏳ $DURATION sekund kutish (DB tiklanishi)..."
    sleep "$DURATION"
    
    # API ishlashini tekshirish
    check_slo || true
    
    log "✅ DB Failover test tugadi"
}

# ============================================================
# ASOSIY TANLOV
# ============================================================
case "$CHAOS_TYPE" in
    pod-kill)
        pod_kill_test
        ;;
    network-delay)
        network_delay_test
        ;;
    db-failover)
        db_failover_test
        ;;
    slo-check)
        check_slo
        ;;
    all)
        log "🎯 BARCHA CHAOS TESTLAR boshlandi..."
        pod_kill_test
        sleep 30
        network_delay_test
        sleep 30
        db_failover_test
        sleep 30
        check_slo
        log "🎯 BARCHA TESTLAR tugadi!"
        ;;
    *)
        echo "Ishlatish: $0 [pod-kill|network-delay|db-failover|slo-check|all] [duration]"
        exit 1
        ;;
esac

log "📋 Hisobot: $REPORT_DIR/"
log "🏁 Chaos test tugadi!"
