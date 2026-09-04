"""
Ruxsatlar (Rollar matritsasi) yordamchi moduli
Direktor/sotuvchi/kassir/omborchi/haydovchi/buxgalter rollari uchun
"""
from typing import Optional

from config import ADMIN_IDS, role_can_view, role_can_edit, role_see_cost


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
    """
    from database.session import get_db_session

    user = getattr(message_or_cb, "from_user", None)
    if user is None:
        return False
    telegram_id = user.id

    with get_db_session() as db:
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
