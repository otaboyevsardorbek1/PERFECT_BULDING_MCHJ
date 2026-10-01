#!/bin/bash

# =====================================================
# PERFECT_BULDING_MCHJ - Barcha xizmatlarni ishga tushirish
# =====================================================

set -e  # Xatolikda to'xtatish

# Rangli chiqish uchun
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   PERFECT_BULDING_MCHJ - STARTUP     ${NC}"
echo -e "${BLUE}========================================${NC}"

# Loyiha ildiz papkasiga o'tish
cd "$(dirname "$0")"

# =====================================================
# 1. O'zgaruvchilarni yuklash
# =====================================================
if [ -f .env ]; then
    echo -e "${GREEN}✓ .env fayl topildi, yuklanmoqda...${NC}"
    export $(grep -v '^#' .env | xargs)
else
    echo -e "${YELLOW}⚠ .env fayl topilmadi, standart sozlamalar ishlatiladi${NC}"
fi

# =====================================================
# 2. Python virtual muhitni tekshirish
# =====================================================
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ Virtual muhit topilmadi, yaratilmoqda...${NC}"
    python3 -m venv venv
fi

echo -e "${GREEN}✓ Virtual muhit aktivlashtirilmoqda...${NC}"
source venv/bin/activate

# =====================================================
# 3. Kerakli paketlarni o'rnatish
# =====================================================
if [ -f "construction_factory_bot/requirements.txt" ]; then
    echo -e "${GREEN}✓ Kerakli paketlar o'rnatilmoqda...${NC}"
    pip install -r construction_factory_bot/requirements.txt
    pip install flask-cors gunicorn  # Qo'shimcha paketlar
fi

# =====================================================
# 4. Ma'lumotlar bazasini tekshirish
# =====================================================
if [ ! -f "construction_factory_bot/database/construction.db" ]; then
    echo -e "${YELLOW}⚠ Ma'lumotlar bazasi topilmadi, yaratilmoqda...${NC}"
    cd construction_factory_bot
    python -c "from database.models import init_db; init_db()" || true
    cd ..
fi

# =====================================================
# 5. PID fayllar uchun papka yaratish
# =====================================================
mkdir -p logs
mkdir -p pids

# =====================================================
# 6. Telegram Botni ishga tushirish
# =====================================================
echo -e "${BLUE}▶ Telegram bot ishga tushirilmoqda...${NC}"
cd construction_factory_bot

# Eski jarayonni o'chirish (agar mavjud bo'lsa)
if [ -f "../pids/bot.pid" ]; then
    OLD_PID=$(cat ../pids/bot.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Eski bot jarayoni to'xtatilmoqda (PID: $OLD_PID)${NC}"
        kill -15 $OLD_PID 2>/dev/null || true
        sleep 2
    fi
fi

# Botni ishga tushirish (nohup orqali)
nohup python main.py > ../logs/bot.log 2>&1 &
BOT_PID=$!
echo $BOT_PID > ../pids/bot.pid
echo -e "${GREEN}✓ Bot ishga tushdi (PID: $BOT_PID)${NC}"
cd ..

# =====================================================
# 7. Web Dashboard (Backend) ni ishga tushirish
# =====================================================
echo -e "${BLUE}▶ Web Dashboard (Backend) ishga tushirilmoqda...${NC}"
cd construction_factory_bot/dashboard

# Eski jarayonni o'chirish
if [ -f "../../pids/backend.pid" ]; then
    OLD_PID=$(cat ../../pids/backend.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Eski backend jarayoni to'xtatilmoqda (PID: $OLD_PID)${NC}"
        kill -15 $OLD_PID 2>/dev/null || true
        sleep 2
    fi
fi

# Backendni ishga tushirish (Gunicorn orqali)
if command -v gunicorn &> /dev/null; then
    nohup gunicorn -w 4 -b 0.0.0.0:5000 app:app > ../../logs/backend.log 2>&1 &
else
    nohup python app.py > ../../logs/backend.log 2>&1 &
fi
BACKEND_PID=$!
echo $BACKEND_PID > ../../pids/backend.pid
echo -e "${GREEN}✓ Backend ishga tushdi (PID: $BACKEND_PID) - http://localhost:5000${NC}"
cd ../..

# =====================================================
# 8. Frontend (Node.js) ni ishga tushirish
# =====================================================
if [ -d "construction_factory_bot/web" ]; then
    echo -e "${BLUE}▶ Frontend ishga tushirilmoqda...${NC}"
    cd construction_factory_bot/web
    
    # Node.js paketlarini o'rnatish (agar kerak bo'lsa)
    if [ -f "package.json" ] && [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}⚠ Node.js paketlari o'rnatilmoqda...${NC}"
        npm install
    fi
    
    # Eski jarayonni o'chirish
    if [ -f "../../pids/frontend.pid" ]; then
        OLD_PID=$(cat ../../pids/frontend.pid)
        if ps -p $OLD_PID > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠ Eski frontend jarayoni to'xtatilmoqda (PID: $OLD_PID)${NC}"
            kill -15 $OLD_PID 2>/dev/null || true
            sleep 2
        fi
    fi
    
    # Frontendni ishga tushirish
    if [ -f "server.js" ]; then
        nohup node server.js > ../../logs/frontend.log 2>&1 &
    elif [ -f "public/index.html" ]; then
        # Oddiy static server
        if command -v python3 &> /dev/null; then
            nohup python3 -m http.server 3000 --directory public > ../../logs/frontend.log 2>&1 &
        else
            nohup npx serve public -l 3000 > ../../logs/frontend.log 2>&1 &
        fi
    fi
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../../pids/frontend.pid
    echo -e "${GREEN}✓ Frontend ishga tushdi (PID: $FRONTEND_PID) - http://localhost:3000${NC}"
    cd ../..
else
    echo -e "${YELLOW}⚠ Web papkasi topilmadi, frontend ishga tushirilmadi${NC}"
fi

# =====================================================
# 9. Xizmatlar holatini ko'rsatish
# =====================================================
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ BARCHA XIZMATLAR ISHGA TUSHDI!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}📊 Xizmatlar:${NC}"
echo -e "  🤖 Bot         : ${GREEN}http://t.me/your_bot_username${NC} (PID: $(cat pids/bot.pid 2>/dev/null || echo 'N/A'))"
echo -e "  🖥️ Backend    : ${GREEN}http://localhost:5000${NC} (PID: $(cat pids/backend.pid 2>/dev/null || echo 'N/A'))"
echo -e "  🌐 Frontend   : ${GREEN}http://localhost:3000${NC} (PID: $(cat pids/frontend.pid 2>/dev/null || echo 'N/A'))"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}📝 Log fayllar:${NC}"
echo -e "  Bot:     ${BLUE}logs/bot.log${NC}"
echo -e "  Backend: ${BLUE}logs/backend.log${NC}"
echo -e "  Frontend:${BLUE}logs/frontend.log${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}⏹ To'xtatish uchun: ./stop.sh${NC}"