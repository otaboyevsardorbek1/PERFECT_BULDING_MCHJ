#!/bin/bash

# =====================================================
# PERFECT_BULDING_MCHJ - Xizmatlar holati
# =====================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   PERFECT_BULDING_MCHJ - STATUS     ${NC}"
echo -e "${BLUE}========================================${NC}"

cd "$(dirname "$0")"

check_service() {
    NAME=$1
    PID_FILE=$2
    PORT=$3
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat $PID_FILE)
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "  ${GREEN}●${NC} $NAME: ${GREEN}Ishlayapti${NC} (PID: $PID"
            if [ ! -z "$PORT" ]; then
                echo -e "    ${BLUE}→${NC} http://localhost:$PORT"
            fi
        else
            echo -e "  ${RED}●${NC} $NAME: ${RED}To'xtagan${NC} (PID: $PID)"
        fi
    else
        echo -e "  ${RED}●${NC} $NAME: ${RED}Ishga tushmagan${NC}"
    fi
}

check_service "Bot" "pids/bot.pid"
check_service "Backend" "pids/backend.pid" "5000"
check_service "Frontend" "pids/frontend.pid" "3000"

echo -e "${BLUE}========================================${NC}"