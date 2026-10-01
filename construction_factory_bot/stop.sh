#!/bin/bash

# =====================================================
# PERFECT_BULDING_MCHJ - Barcha xizmatlarni to'xtatish
# =====================================================

# Rangli chiqish uchun
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   PERFECT_BULDING_MCHJ - SHUTDOWN    ${NC}"
echo -e "${BLUE}========================================${NC}"

# Loyiha ildiz papkasiga o'tish
cd "$(dirname "$0")"

# =====================================================
# 1. Telegram Botni to'xtatish
# =====================================================
if [ -f "pids/bot.pid" ]; then
    BOT_PID=$(cat pids/bot.pid)
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⏹ Bot to'xtatilmoqda (PID: $BOT_PID)${NC}"
        kill -15 $BOT_PID 2>/dev/null || true
        sleep 2
        # Majburiy o'chirish (agar o'chmasa)
        if ps -p $BOT_PID > /dev/null 2>&1; then
            echo -e "${RED}⚠ Bot majburiy to'xtatilmoqda...${NC}"
            kill -9 $BOT_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ Bot to'xtatildi${NC}"
    else
        echo -e "${YELLOW}⚠ Bot jarayoni topilmadi (PID: $BOT_PID)${NC}"
    fi
    rm -f pids/bot.pid
else
    echo -e "${YELLOW}⚠ Bot PID fayli topilmadi${NC}"
fi

# =====================================================
# 2. Backend (Gunicorn/Flask) ni to'xtatish
# =====================================================
if [ -f "pids/backend.pid" ]; then
    BACKEND_PID=$(cat pids/backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⏹ Backend to'xtatilmoqda (PID: $BACKEND_PID)${NC}"
        kill -15 $BACKEND_PID 2>/dev/null || true
        sleep 2
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            echo -e "${RED}⚠ Backend majburiy to'xtatilmoqda...${NC}"
            kill -9 $BACKEND_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ Backend to'xtatildi${NC}"
    else
        echo -e "${YELLOW}⚠ Backend jarayoni topilmadi (PID: $BACKEND_PID)${NC}"
    fi
    rm -f pids/backend.pid
else
    echo -e "${YELLOW}⚠ Backend PID fayli topilmadi${NC}"
fi

# =====================================================
# 3. Frontend (Node.js) ni to'xtatish
# =====================================================
if [ -f "pids/frontend.pid" ]; then
    FRONTEND_PID=$(cat pids/frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⏹ Frontend to'xtatilmoqda (PID: $FRONTEND_PID)${NC}"
        kill -15 $FRONTEND_PID 2>/dev/null || true
        sleep 2
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            echo -e "${RED}⚠ Frontend majburiy to'xtatilmoqda...${NC}"
            kill -9 $FRONTEND_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ Frontend to'xtatildi${NC}"
    else
        echo -e "${YELLOW}⚠ Frontend jarayoni topilmadi (PID: $FRONTEND_PID)${NC}"
    fi
    rm -f pids/frontend.pid
else
    echo -e "${YELLOW}⚠ Frontend PID fayli topilmadi${NC}"
fi

# =====================================================
# 4. Qolgan jarayonlarni to'xtatish (agar mavjud bo'lsa)
# =====================================================
echo -e "${YELLOW}🔍 Qolgan jarayonlar tekshirilmoqda...${NC}"

# Barcha python jarayonlarini tekshirish (faqat loyiha bilan bog'liq)
PIDS=$(ps aux | grep -E "main.py|app.py|gunicorn" | grep -v grep | awk '{print $2}')
if [ ! -z "$PIDS" ]; then
    echo -e "${YELLOW}⚠ Qolgan jarayonlar topildi, to'xtatilmoqda...${NC}"
    for PID in $PIDS; do
        kill -15 $PID 2>/dev/null || true
    done
    sleep 2
fi

# Node.js jarayonlarini tekshirish (faqat loyiha bilan bog'liq)
PIDS=$(ps aux | grep -E "server.js|serve" | grep -v grep | awk '{print $2}')
if [ ! -z "$PIDS" ]; then
    for PID in $PIDS; do
        kill -15 $PID 2>/dev/null || true
    done
    sleep 2
fi

# =====================================================
# 5. Portlarni bo'shatish
# =====================================================
echo -e "${YELLOW}🔍 Portlar tekshirilmoqda...${NC}"

# 5000-port (Backend)
if command -v lsof &> /dev/null; then
    if lsof -i:5000 > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ 5000-port band, bo'shatilmoqda...${NC}"
        fuser -k 5000/tcp 2>/dev/null || true
    fi
    # 3000-port (Frontend)
    if lsof -i:3000 > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ 3000-port band, bo'shatilmoqda...${NC}"
        fuser -k 3000/tcp 2>/dev/null || true
    fi
fi

# =====================================================
# 6. Virtual muhitni o'chirish (ixtiyoriy)
# =====================================================
if [ "$1" == "--deactivate" ]; then
    echo -e "${YELLOW}⚠ Virtual muhit o'chirilmoqda...${NC}"
    deactivate 2>/dev/null || true
fi

# =====================================================
# 7. Xulosa
# =====================================================
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ BARCHA XIZMATLAR TO'XTATILDI!${NC}"
echo -e "${BLUE}========================================${NC}"

# Qolgan jarayonlarni tekshirish
REMAINING=$(ps aux | grep -E "main.py|app.py|gunicorn|server.js" | grep -v grep | wc -l)
if [ $REMAINING -gt 0 ]; then
    echo -e "${RED}⚠ Diqqat! $REMAINING ta jarayon hali ishlayapti:${NC}"
    ps aux | grep -E "main.py|app.py|gunicorn|server.js" | grep -v grep
    echo -e "${YELLOW}Majburiy o'chirish uchun: ./stop.sh --force${NC}"
else
    echo -e "${GREEN}✓ Barcha jarayonlar to'xtatilgan${NC}"
fi
echo -e "${BLUE}========================================${NC}"