"""
Ruxsatlar (Rollar matritsasi) yordamchi moduli
Direktor/sotuvchi/kassir/omborchi/haydovchi/buxgalter rollari uchun

v4: Bot login/parol xavfsizligi bilan integratsiya.
BOT_AUTH_ENABLED=true bo'lsa, har bir ruxsat tekshiruvidan OLDIN sessiya
holati tekshiriladi — sessiya yo'q/yoki o'lgan foydalanuvchiga HECH QANDAY
daraja berilmaydi (faqat /login, /help, /cancel ishlaydi).
"""
from typing import Optional

from config import ADMIN_IDS, role_can_view, role_can_edit, role_see_cost

# Sessiya talab qilinmaydigan komandalar (login oldi)
# /start — xush kelibsiz + login ko'rsatmasi, /help, /cancel, /login, /logout, /sessiya, /parol
_SESSION_FREE_COMMANDS = {
    "/start", "/help", "/cancel", "/login", "/logout", "/sessiya", "/parol",
    # Menyudagi auth tugmalari (reply keyboard)
    "🔐 Kirish (login)", "📊 Sessiya holati", "🚪 Chiqish (logout)",
}
# Kichik harflar bilan oldindan hisoblangan to'plam (tezkor qiyoslash uchun)
_SESSION_FREE_LOWER = {c.lower() for c in _SESSION_FREE_COMMANDS}


def is_session_free_text(text: Optional[str]) -> bool:
    """Xabar sessiya talab qilmaydigan buyruq/menyu tugmasimi?

    Ikkala ko'rinish ham tekshiriladi:
      - to'liq matn (reply keyboard tugmalari: "🔐 Kirish (login)")
      - birinchi token (buyruqlar: "/login", "/login@botname")

    MUHIM: main.py'dagi global sessiya middleware'i ham shu funksiyadan
    foydalanadi — aks holda login oldi MENYU TUGMALARI sessiyasiz bloklanib
    qoladi (faqat /buyruq shakli o'tadi).
    """
    clean = (text or "").strip()
    if not clean:
        return False
    if clean.lower() in _SESSION_FREE_LOWER:
        return True
    cmd = clean.split("@", 1)[0].split()
    return bool(cmd) and cmd[0].lower() in _SESSION_FREE_LOWER


def get_user_role(db, telegram_id: int) -> str:
    """
    Telegram foydalanuvchisining rolini aniqlash:
    - ADMIN_IDS dagi foydalanuvchi -> direktor
    - Employee jadvalida role yozilgan bo'lsa -> shu rol
    - Aks holda -> ishchi
    """
    if telegram_id in ADMIN_IDS:
        return "direktor"

    from database import models
    employee = db.query(models.Employee).filter(
        models.Employee.telegram_id == telegram_id
    ).first()
    if employee:
        if employee.is_admin:
            return "direktor"
        return employee.role or "ishchi"
    return "ishchi"


def session_is_valid(db, telegram_id: int, text: Optional[str] = None) -> bool:
    """Bot sessiyasi yaroqlimi?

    v4 xavfsizlik: BOT_AUTH_ENABLED=true bo'lsa foydalanuvchi faol sessiyaga
    ega bo'lishi shart. Login oldi komandalarida (/start, /help, /login...)
    sessiya talab qilinmaydi.
    """
    # Login oldi komandalar doim ochiq (buyruq tokeni yoki to'liq menyu tugma matni)
    if is_session_free_text(text):
        return True

    from utils import bot_auth
    if not bot_auth.is_bot_auth_enabled():
        return True  # eski rejim: sessiya talab qilinmaydi
    return bot_auth.check_session_permission(db, telegram_id) is None


def user_can_view(db, telegram_id: int, module: str) -> bool:
    """Foydalanuvchi modulni ko'ra oladimi"""
    role = get_user_role(db, telegram_id)
    return role_can_view(role, module)


def user_can_edit(db, telegram_id: int, module: str) -> bool:
    """Foydalanuvchi modulda o'zgartirish qila oladimi"""
    role = get_user_role(db, telegram_id)
    return role_can_edit(role, module)


def user_see_cost(db, telegram_id: int) -> bool:
    """Foydalanuvchi tannarxni ko'ra oladimi"""
    role = get_user_role(db, telegram_id)
    return role_see_cost(role)


def role_label(db, telegram_id: int) -> str:
    """Foydalanuvchi roli yorlig'i"""
    from config import get_role_label
    return get_role_label(get_user_role(db, telegram_id))


async def ensure_access(message_or_cb, module: str, edit: bool = False) -> bool:
    """
    Bot handlerlari uchun ruxsatni tekshiradi.
    Ruxsat bo'lmasa xabar yuborib False qaytaradi.
    message_or_cb: Message yoki CallbackQuery

    v4: avval SESSIYA tekshiriladi — sessiya yo'q bo'lsa foydalanuvchi
    /login ga yo'naltiriladi (TZ: sessiya tugaganda darajalar bekor bo'ladi).
    """
    from database.session import get_db_session

    user = getattr(message_or_cb, "from_user", None)
    if user is None:
        return False
    telegram_id = user.id

    with get_db_session() as db:
        # ---- v4: Sessiya tekshiruvi (login/parol xavfsizligi) ----
        if not session_is_valid(db, telegram_id, getattr(message_or_cb, "text", None)):
            text = (
                "🔐 **SESSIYA YAROQSIZ yoki TUGAGAN**\n\n"
                "Xavfsizlik uchun har bir amal faol sessiya talab qiladi.\n"
                "Sessiya 5-30 daqiqa yashaydi va tugaganda barcha darajalar bekor bo'ladi.\n\n"
                "➡️ Tizimga kirish uchun: /login"
            )
            answer = getattr(message_or_cb, "answer", None)
            if answer:
                if hasattr(message_or_cb, "message"):
                    await message_or_cb.message.answer(text, parse_mode="Markdown")
                else:
                    await answer(text, parse_mode="Markdown")
            return False

        role = get_user_role(db, telegram_id)
        if edit:
            ok = role_can_edit(role, module)
        else:
            ok = role_can_view(role, module)
        if not ok:
            label = role_label(db, telegram_id)
            text = f"❌ Ruxsat yo'q!\nSizning rolingiz: {label}\nBu bo'lim ({module}) sizga ochiq emas."
            answer = getattr(message_or_cb, "answer", None)
            if answer:
                if hasattr(message_or_cb, "message"):
                    await message_or_cb.message.answer(text)
                else:
                    await answer(text)
            return False
    return True
