#!/usr/bin/env bash

# =========================================================
#  Claude Code + OpenRouter avtomatik sozlash skripti
# =========================================================

set -e

# ---------- Ranglar ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ---------- Chiroyli chiqarish ----------
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# =========================================================
# 1. API KEY ni so'rash
# =========================================================
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}  Claude Code + OpenRouter Sozlash${NC}"
echo -e "${CYAN}=========================================${NC}"
echo

if [ -z "$OPENROUTER_API_KEY" ]; then
    read -r -p "🔑 OpenRouter API key'ingizni kiriting: " OPENROUTER_API_KEY
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    error "API key bo'sh bo'lishi mumkin emas!"
fi

# sk-or- bilan boshlanishini tekshirish (ixtiyoriy)
if [[ ! "$OPENROUTER_API_KEY" =~ ^sk-or- ]]; then
    warn "API key 'sk-or-' bilan boshlanmadi. Baribir davom etamiz."
fi

# =========================================================
# 2. Model tanlash
# =========================================================
echo
echo -e "${CYAN}Qaysi modelni ishlatmoqchisiz?${NC}"
echo "  1) anthropic/claude-sonnet-4"
echo "  2) anthropic/claude-3.5-sonnet"
echo "  3) anthropic/claude-3.5-haiku"
echo "  4) Boshqa (o'zingiz yozasiz)"
read -r -p "Tanlang [1-4, default=1]: " MODEL_CHOICE

case "$MODEL_CHOICE" in
    2) ANTHROPIC_MODEL="anthropic/claude-3.5-sonnet" ;;
    3) ANTHROPIC_MODEL="anthropic/claude-3.5-haiku" ;;
    4)
        read -r -p "Model nomini kiriting (masalan: anthropic/claude-sonnet-4): " ANTHROPIC_MODEL
        ;;
    *) ANTHROPIC_MODEL="anthropic/claude-sonnet-4" ;;
esac

# Kichik/tez model (background vazifalar uchun)
ANTHROPIC_SMALL_FAST_MODEL="anthropic/claude-3.5-haiku"

# =========================================================
# 3. Shell faylini aniqlash
# =========================================================
CURRENT_SHELL="$(basename "$SHELL")"
case "$CURRENT_SHELL" in
    zsh)  PROFILE_FILE="$HOME/.zshrc" ;;
    bash) PROFILE_FILE="$HOME/.bashrc" ;;
    *)    PROFILE_FILE="$HOME/.profile" ;;
esac

info "Shell: $CURRENT_SHELL"
info "Profil fayli: $PROFILE_FILE"

# =========================================================
# 4. Eski sozlamalarni tozalash
# =========================================================
info "Eski sozlamalar tozalanmoqda..."
if [ -f "$PROFILE_FILE" ]; then
    # Belgilar orasidagi blokni o'chirish
    sed -i.bak '/# >>> Claude-OpenRouter START >>>/,/# <<< Claude-OpenRouter END <<</d' "$PROFILE_FILE"
    success "Eski blok o'chirildi (zaxira: ${PROFILE_FILE}.bak)"
fi

# =========================================================
# 5. Yangi sozlamalarni yozish
# =========================================================
info "Yangi sozlamalar yozilmoqda..."

cat >> "$PROFILE_FILE" <<EOF

# >>> Claude-OpenRouter START >>>
# Avtomatik yaratilgan: $(date '+%Y-%m-%d %H:%M:%S')
export OPENROUTER_API_KEY="$OPENROUTER_API_KEY"
export ANTHROPIC_BASE_URL="https://openrouter.ai/api/v1"
export ANTHROPIC_AUTH_TOKEN="\$OPENROUTER_API_KEY"
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL="$ANTHROPIC_MODEL"
export ANTHROPIC_SMALL_FAST_MODEL="$ANTHROPIC_SMALL_FAST_MODEL"
# <<< Claude-OpenRouter END <<<
EOF

success "Sozlamalar $PROFILE_FILE ga yozildi."

# =========================================================
# 6. Joriy sessiyaga ham qo'llash
# =========================================================
export OPENROUTER_API_KEY="$OPENROUTER_API_KEY"
export ANTHROPIC_BASE_URL="https://openrouter.ai/api/v1"
export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL="$ANTHROPIC_MODEL"
export ANTHROPIC_SMALL_FAST_MODEL="$ANTHROPIC_SMALL_FAST_MODEL"

# =========================================================
# 7. Claude CLI tekshirish
# =========================================================
echo
info "Claude CLI tekshirilmoqda..."
if command -v claude >/dev/null 2>&1; then
    success "Claude CLI topildi: $(command -v claude)"
else
    warn "Claude CLI topilmadi."
    read -r -p "O'rnatishni xohlaysizmi? (y/n): " INSTALL_CLAUDE
    if [[ "$INSTALL_CLAUDE" =~ ^[Yy]$ ]]; then
        if command -v npm >/dev/null 2>&1; then
            info "npm orqali o'rnatilmoqda..."
            npm install -g @anthropic-ai/claude-code
            success "Claude CLI o'rnatildi."
        else
            error "npm topilmadi. Iltimos, avval Node.js o'rnating."
        fi
    fi
fi

# =========================================================
# 8. Ulanishni tekshirish (ixtiyoriy)
# =========================================================
echo
read -r -p "🔍 OpenRouter bilan ulanishni sinab ko'rishni xohlaysizmi? (y/n): " TEST_CONN
if [[ "$TEST_CONN" =~ ^[Yy]$ ]]; then
    info "Test so'rovi yuborilmoqda..."
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "https://openrouter.ai/api/v1/chat/completions" \
        -H "Authorization: Bearer $OPENROUTER_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "model": "'"$ANTHROPIC_MODEL"'",
            "messages": [{"role":"user","content":"ping"}],
            "max_tokens": 5
        }')

    if [ "$RESPONSE" = "200" ]; then
        success "Ulanish muvaffaqiyatli! (HTTP 200)"
    else
        warn "Javob kodi: $RESPONSE. API key yoki kreditni tekshiring."
    fi
fi

# =========================================================
# 9. Yakuniy xabar
# =========================================================
echo
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  ✅ Sozlash muvaffaqiyatli yakunlandi!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo
echo -e "📌 Ishlatilayotgan model : ${CYAN}$ANTHROPIC_MODEL${NC}"
echo -e "📌 Profil fayli         : ${CYAN}$PROFILE_FILE${NC}"
echo
echo -e "${YELLOW}Keyingi qadamlar:${NC}"
echo -e "  1) Terminalni qayta oching yoki quyidagini bajaring:"
echo -e "     ${CYAN}source $PROFILE_FILE${NC}"
echo -e "  2) So'ng Claude'ni ishga tushiring:"
echo -e "     ${CYAN}claude${NC}"
echo

