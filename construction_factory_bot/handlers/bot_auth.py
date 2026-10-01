"""
Bot LOGIN/LOGOUT/SESSIYA handlerlari (v4)

TZ xavfsizlik talablariga ko'ra har bir xodim botda /login orqali PAROL
bilan tasdiqlanadi. Sessiya 5-30 daqiqa yashaydi va tugaganda (muddat,
harakatsizlik) yoki logout qilinganda barcha darajalar bekor bo'ladi.

Komandalar:
  /login     — telefon raqami + parol bilan sessiya ochish (2FA bo'lsa kod ham)
  /logout    — sessiyani bekor qilish (darajalar darhol o'chadi)
  /sessiya   — joriy sessiya holatini ko'rish
  /parol     — o'z parolini o'zgartirish (parol bilgan kishi)
  /2fa       — Google Authenticator (2FA) yoqish / o'chirish

2FA (v4.2): "Direktor va kassir uchun Google Authenticator" — parol to'g'ri
bo'lsa ham 6 xonali TOTP kod talab qilinadi. Kod server tomonda tekshiriladi.

Parol saqlanishi: PBKDF2 (dashboard/auth.py bilan bir xil format) —
bir parol ham web dashboard, ham bot uchun ishlaydi.
"""
import logging

from aiogram import types, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from config import (
    BOT_SESSION_MINUTES,
    BOT_SESSION_IDLE_MINUTES,
)
from database.session import get_db_session
from database import models
from utils import bot_auth
from utils.bot_auth import BOT_LOGIN_LOCKOUT_MINUTES

logger = logging.getLogger(__name__)


class BotAuthStates(StatesGroup):
    waiting_phone = State()
    waiting_password = State()
    waiting_otp = State()              # 2FA: Google Authenticator kodini kiritish (login)
    waiting_old_password = State()
    waiting_new_password = State()
    waiting_new_password_repeat = State()
    waiting_2fa_confirm = State()      # /2fa yoqish: yangi QR kodni tasdiqlash
    waiting_2fa_disable = State()      # /2fa o'chirish: joriy kodni kiritish


# =============== YORDAMCHILAR ===============
def _find_employee_by_phone(db, phone: str):
    """Telefon raqami bo'yicha xodimni topish (formatdan qat'iy nazar)"""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return None
    for emp in db.query(models.Employee).all():
        if "".join(ch for ch in (emp.phone_number or "") if ch.isdigit()) == digits:
            return emp
    return None


def _find_employee_by_telegram(db, telegram_id: int):
    return db.query(models.Employee).filter(
        models.Employee.telegram_id == telegram_id
    ).first()


def _has_active_session(db, telegram_id: int) -> bool:
    return bot_auth.get_active_bot_session(db, telegram_id) is not None


# =============== /LOGIN ===============
async def cmd_login(message: types.Message, state: FSMContext):
    """Botga kirish: telefon + parol"""
    telegram_id = message.from_user.id

    # Parol talabi o'chirilgan bo'lsa (eski rejim)
    if not bot_auth.is_bot_auth_enabled():
        await message.answer(
            "ℹ️ Bot xavfsizlik rejimi o'chirilgan (BOT_AUTH_ENABLED=false).\n"
            "Login shart emas."
        )
        return

    with get_db_session() as db:
        if _has_active_session(db, telegram_id):
            await message.answer(
                "✅ Siz allaqachon tizimga kirgansiz!\n\n"
                "📊 Sessiya holati: /sessiya\n"
                "🚪 Chiqish: /logout"
            )
            return

        # Blok tekshiruvi
        lock_remaining = bot_auth.is_login_locked(telegram_id)
        if lock_remaining:
            await message.answer(
                f"🔒 Hisobingiz vaqtincha bloklandi.\n"
                f"⏳ Taxminan {lock_remaining // 60} daqiqa {lock_remaining % 60} sekunddan "
                f"keyin qayta urinib ko'ring."
            )
            return

        # Xodim allaqachon bog'langanmi (telegram_id orqali) — shunchaki parol so'raymiz
        employee = _find_employee_by_telegram(db, telegram_id)
        if employee and employee.phone_number:
            await state.set_state(BotAuthStates.waiting_password)
            await state.update_data(phone=employee.phone_number)
            await message.answer(
                "🔐 **TIZIMGA KIRISH**\n\n"
                f"👋 Assalomu alaykum, {employee.full_name}!\n\n"
                "Parolingizni kiriting:\n\n"
                "_Parolni xodimlar bo'limi bergan bo'ladi yoki /parol bilan o'zingiz o'rnatgan bo'lasiz._",
                parse_mode="Markdown",
            )
            return

        # Telegram ID bog'lanmagan — telefon raqamini so'raymiz
        await state.set_state(BotAuthStates.waiting_phone)
        await message.answer(
            "🔐 **TIZIMGA KIRISH**\n\n"
            "Telefon raqamingizni kiriting (masalan: +998901234567):"
        )


async def process_login_phone(message: types.Message, state: FSMContext):
    """Login 1-qadam: telefon raqamini qabul qilish"""
    phone = (message.text or "").strip()
    telegram_id = message.from_user.id

    # Blok tekshiruvi
    lock_remaining = bot_auth.is_login_locked(telegram_id)
    if lock_remaining:
        await state.clear()
        await message.answer(
            f"🔒 Hisobingiz vaqtincha bloklandi.\n"
            f"⏳ Taxminan {lock_remaining // 60} daqiqa {lock_remaining % 60} sekunddan "
            f"keyin qayta urinib ko'ring."
        )
        return

    with get_db_session() as db:
        employee = _find_employee_by_phone(db, phone)

    if employee is None:
        await message.answer(
            "❌ Bu telefon raqam bilan xodim topilmadi.\n"
            "Qayta kiriting yoki /cancel bilan bekor qiling:"
        )
        return

    await state.set_state(BotAuthStates.waiting_password)
    await state.update_data(phone=phone)
    await message.answer(
        f"👤 Xodim: **{employee.full_name}**\n\n"
        "Endi parolingizni kiriting:"
    )


async def process_login_password(message: types.Message, state: FSMContext):
    """Login 2-qadam: parolni tekshirish va sessiya ochish"""
    password = (message.text or "").strip()
    telegram_id = message.from_user.id
    data = await state.get_data()
    phone = data.get("phone", "")

    # Xavfsizlik: parol xabarini darhol o'chirishga urinish (admin yozishini cheklash mumkin emas,
    # lekin foydalanuvchiga eslatamiz)
    await state.clear()

    with get_db_session() as db:
        employee = _find_employee_by_phone(db, phone)
        if employee is None:
            await message.answer("❌ Xodim topilmadi. /login bilan qayta boshlang.")
            return

        # Blok tekshiruvi
        lock_remaining = bot_auth.is_login_locked(telegram_id)
        if lock_remaining:
            await message.answer(
                f"🔒 Hisobingiz vaqtincha bloklandi.\n"
                f"⏳ Taxminan {lock_remaining // 60} daqiqa {lock_remaining % 60} sekunddan "
                f"keyin qayta urinib ko'ring."
            )
            return

        # Parol yo'q bo'lsa — birinchi marta kirishda o'rnatish taklif qilinadi
        if not bot_auth.employee_has_password(db, employee):
            # Bootstrap: bog'lanmagan telegram ID'ni bog'laymiz, aks holda
            # /parol xodimni topolmaydi (deadlock). Band bo'lsa — admin.
            claimed = bot_auth.claim_employee_telegram(db, employee, telegram_id)
            if claimed:
                await message.answer(
                    "⚠️ Sizda hali parol o'rnatilmagan.\n\n"
                    "✅ Telegram hisobingiz tizimga bog'landi.\n"
                    "Parolni o'rnatish uchun /parol buyrug'ini yuboring.\n"
                    "(Keyin shu parol bilan /login qilasiz)"
                )
            else:
                await message.answer(
                    "⚠️ Sizda hali parol o'rnatilmagan.\n\n"
                    "Bu telefon raqami boshqa Telegram hisobiga bog'langan.\n"
                    "Admin bilan bog'laning."
                )
            return

        # Parolni tekshirish
        if not bot_auth.verify_password(password, employee.password_hash):
            remaining = bot_auth.register_failed_login(telegram_id)
            if remaining <= 0:
                await message.answer(
                    "🔒 **Hisobingiz bloklandi!**\n\n"
                    f"Xato parol {bot_auth.BOT_LOGIN_MAX_ATTEMPTS} marta kiritildi.\n"
                    f"⏳ {BOT_LOGIN_LOCKOUT_MINUTES} daqiqadan keyin qayta urinib ko'ring."
                )
            else:
                await message.answer(
                    f"❌ Parol noto'g'ri!\n"
                    f"Qolgan urinishlar: {remaining} ta\n\n"
                    "Qayta /login bering."
                )
            return

        # Muvaffaqiyatli login (parol to'g'ri) — 2FA tekshiruvi
        bot_auth.reset_login_attempts(telegram_id)

        # 2FA (Google Authenticator): parol to'g'ri, endi 6 xonali kod so'raladi
        if bot_auth.employee_2fa_enabled(employee):
            await state.set_state(BotAuthStates.waiting_otp)
            await state.update_data(phone=phone)
            await message.answer(
                "🔐 **2FA TASDIQLASH**\n\n"
                "Hisobingizda Google Authenticator yoqilgan.\n"
                "Ilovadagi joriy **6 xonali kodni** kiriting:\n\n"
                "_Kod har 30 soniyada yangilanadi. /cancel bilan bekor qilish mumkin._",
                parse_mode="Markdown",
            )
            return

        await _complete_bot_login(db, employee, telegram_id, message)


async def process_login_otp(message: types.Message, state: FSMContext):
    """Login 2FA bosqichi: Google Authenticator kodini tekshirib sessiya ochish"""
    code = (message.text or "").strip()
    telegram_id = message.from_user.id
    data = await state.get_data()
    phone = data.get("phone", "")
    await state.clear()

    with get_db_session() as db:
        employee = _find_employee_by_phone(db, phone)
        if employee is None:
            await message.answer("❌ Xodim topilmadi. /login bilan qayta boshlang.")
            return
        if not bot_auth.employee_2fa_enabled(employee):
            await message.answer("ℹ️ 2FA holati o'zgardi. Qayta /login bering.")
            return
        if not bot_auth.verify_2fa_code(employee, code):
            await message.answer(
                "❌ Kod noto'g'ri yoki muddati o'tgan.\n\n"
                "Google Authenticator'dagi joriy kodni kiriting: /login",
                parse_mode="Markdown",
            )
            return
        await _complete_bot_login(db, employee, telegram_id, message)


async def _complete_bot_login(db, employee, telegram_id: int, message: types.Message):
    """Login'ning oxirgi bosqichi: telegram ID bog'lash, sessiya ochish, xabar"""
    # Telegram ID hali bog'lanmagan bo'lsa bog'laymiz (faqat ACTIVE xodimlarga)
    if employee.telegram_id != telegram_id:
        if employee.telegram_id and employee.telegram_id != telegram_id:
            # Bu raqam boshqa telegram hisobiga bog'langan — admin qo'shib qo'ysin
            await message.answer(
                "⚠️ Bu raqam boshqa Telegram hisobiga bog'langan.\n"
                "Admin bilan bog'laning yoki admin panelda xodimni yangilang."
            )
            return
        employee.telegram_id = telegram_id
        db.commit()

    if employee.status != models.EmployeeStatus.ACTIVE:
        await message.answer(
            "❌ Hisobingiz faol emas (ishdan bo'shatilgan / ta'tilda).\n"
            "Admin bilan bog'laning."
        )
        return

    session = bot_auth.create_bot_session(db, employee, telegram_id)
    role_label = ""
    try:
        from utils.access import role_label as _role_label
        role_label = _role_label(db, telegram_id)
    except Exception:
        role_label = employee.role or "ishchi"

    await message.answer(
        "✅ **MUVAFFAQIYATLI KIRILDINGIZ!**\n\n"
        f"👤 {employee.full_name}\n"
        f"🎭 Rol: {role_label}\n\n"
        f"⏱ Sessiya: **{BOT_SESSION_MINUTES} daqiqa**\n"
        f"💤 Harakatsizlik limiti: {BOT_SESSION_IDLE_MINUTES} daqiqa\n\n"
        "ℹ️ Sessiya tugaganda yoki /logout qilganingizda barcha darajalar "
        "bekor bo'ladi va qayta /login kerak bo'ladi.\n\n"
        "📊 Sessiya holati: /sessiya\n"
        "🚪 Chiqish: /logout"
    )


# =============== /2FA (GOOGLE AUTHENTICATOR) ===============
async def cmd_2fa(message: types.Message, state: FSMContext):
    """2FA holatini ko'rsatadi; yoqish (QR kod) yoki o'chirish jarayonini boshlaydi.

    Faqat faol sessiyasi bor xodimlarga ochiq — 2FA sozlamasi o'zi xavfsizlik
    amali, shuning uchun oldin /login talab qilinadi.
    """
    telegram_id = message.from_user.id

    with get_db_session() as db:
        employee = db.query(models.Employee).filter(
            models.Employee.telegram_id == telegram_id
        ).first()
        if employee is None:
            await message.answer("👤 Siz tizimda xodim sifatida topilmadi. Avval /login qiling.")
            return
        session = bot_auth.get_active_bot_session(db, telegram_id)
        if session is None:
            await message.answer(
                "🔒 **2FA** sozlamasi uchun faol sessiya kerak.\n\n"
                "Avval /login buyrug'i bilan kiring."
            )
            return

        enabled = bot_auth.employee_2fa_enabled(employee)
        if enabled:
            await state.set_state(BotAuthStates.waiting_2fa_disable)
            await state.update_data(phone=employee.phone_number)
            await message.answer(
                "🔐 **2FA (Google Authenticator)**\n\n"
                "✅ Sizning hisobingizda 2FA **yoqilgan**.\n\n"
                "O'chirish uchun ilovadagi joriy **6 xonali kodni** kiriting:\n\n"
                "_Xavfsizlik uchun kod so'raladi. /cancel bilan bekor qilish mumkin._",
                parse_mode="Markdown",
            )
            return

        # Yoqish: yangi secret + QR kod
        from utils.totp import generate_secret, provisioning_uri, qr_png_bytes
        secret = generate_secret()
        employee.otp_secret = secret
        employee.otp_enabled = False
        db.commit()
        uri = provisioning_uri(secret, employee.full_name)
        text = (
            "🔐 **2FA (GOOGLE AUTHENTICATOR)**\n\n"
            "1. Telefoningizga **Google Authenticator** ilovasini o'rnating\n"
            "2. Ilovada **+** → **QR kodni skanerlash** → quyidagi rasmni skanerlang\n"
            "3. Paydo bo'lgan **6 xonali kodni** shu chatga yozing\n\n"
            f"📎 Yoki ushbu kalitni qo'lda kiriting:\n`{secret}`\n\n"
            "_Kodni tasdiqlash bilan 2FA yoqiladi. Telefon yo'qolsa admin bilan bog'laning._"
        )
        png = qr_png_bytes(secret, employee.full_name)
        if png:
            await message.answer_photo(
                types.BufferedInputFile(png, filename="2fa_qr.png"),
                caption=text,
                parse_mode="Markdown",
            )
        else:
            await message.answer(text + "\n\n(QR generatori o'rnatilmagan — kalit yetarli)",
                                 parse_mode="Markdown")
        await state.set_state(BotAuthStates.waiting_2fa_confirm)
        await state.update_data(phone=employee.phone_number)


async def process_2fa_confirm(message: types.Message, state: FSMContext):
    """Yangi QR kod'dan olingan kodni tasdiqlab 2FA'ni yoqadi"""
    code = (message.text or "").strip()
    data = await state.get_data()
    phone = data.get("phone", "")
    await state.clear()

    with get_db_session() as db:
        employee = _find_employee_by_phone(db, phone)
        if employee is None or not getattr(employee, "otp_secret", None):
            await message.answer("❌ 2FA sozlamasi topilmadi. /2fa bilan qayta boshlang.")
            return
        from utils.totp import verify_totp
        if not verify_totp(employee.otp_secret, code):
            await message.answer(
                "❌ Kod noto'g'ri yoki muddati o'tgan.\n\n"
                "Google Authenticator'dagi joriy kodni kiriting yoki /2fa bilan qayta boshlang."
            )
            return
        employee.otp_enabled = True
        db.commit()
        try:
            from database import crud
            crud.create_system_log(db, user_id=employee.telegram_id, user_name=employee.full_name,
                                   action="2FA yoqildi (Google Authenticator)", module="security")
        except Exception:
            pass
    await message.answer(
        "✅ **2FA YOQILDI!**\n\n"
        "Endi har kirishda (bot ham, web dashboard ham) parol + Google Authenticator "
        "kodi talab qilinadi."
    )


async def process_2fa_disable(message: types.Message, state: FSMContext):
    """Joriy kodni tekshirib 2FA'ni o'chiradi"""
    code = (message.text or "").strip()
    data = await state.get_data()
    phone = data.get("phone", "")
    await state.clear()

    with get_db_session() as db:
        employee = _find_employee_by_phone(db, phone)
        if employee is None:
            await message.answer("❌ Xodim topilmadi. /login qiling.")
            return
        if not bot_auth.verify_2fa_code(employee, code):
            await message.answer(
                "❌ Kod noto'g'ri.\n\n"
                "Google Authenticator'dagi joriy kodni kiriting yoki /2fa bilan qayta boshlang."
            )
            return
        employee.otp_secret = None
        employee.otp_enabled = False
        db.commit()
        try:
            bot_auth.revoke_all_employee_bot_sessions(db, employee.id, reason="2fa_disabled")
        except Exception:
            pass
        try:
            from database import crud
            crud.create_system_log(db, user_id=employee.telegram_id, user_name=employee.full_name,
                                   action="2FA o'chirildi", module="security")
        except Exception:
            pass
    await message.answer(
        "✅ **2FA O'CHIRILDI.**\n\n"
        "Xavfsizlik uchun barcha sessiyalar bekor qilindi — qayta kirish uchun /login."
    )


# =============== /LOGOUT ===============
async def cmd_logout(message: types.Message, state: FSMContext):
    """Sessiyani bekor qilish — barcha darajalar darhol o'chadi"""
    telegram_id = message.from_user.id
    await state.clear()

    with get_db_session() as db:
        logged_out = bot_auth.logout_bot_session(db, telegram_id)

    if logged_out:
        await message.answer(
            "🚪 **Tizimdan chiqdingiz.**\n\n"
            "✅ Barcha sessiyalar bekor qilindi.\n"
            "✅ Berilgan darajalar (ruxsatlar) o'chirildi.\n\n"
            "Qayta kirish uchun: /login"
        )
    else:
        await message.answer(
            "ℹ️ Sizda faol sessiya yo'q edi.\n"
            "Kirish uchun: /login"
        )


# =============== /SESSIYA ===============
async def cmd_session_status(message: types.Message):
    """Joriy sessiya holati"""
    telegram_id = message.from_user.id

    with get_db_session() as db:
        session = bot_auth.get_active_bot_session(db, telegram_id)
        if session is None:
            await message.answer(
                "🔴 **FAOL SESSIYA YO'Q**\n\n"
                "Tizimga kirish uchun: /login"
            )
            return
        info = bot_auth.session_to_dict(session)
        employee = db.query(models.Employee).filter(
            models.Employee.id == session.employee_id
        ).first()

    mins_left = info["seconds_left"] // 60
    secs_left = info["seconds_left"] % 60
    idle_min = (info.get("idle_seconds") or 0) // 60
    emp_name = employee.full_name if employee else "—"

    await message.answer(
        "📊 **SESSIYA HOLATI**\n\n"
        f"👤 {emp_name}\n"
        f"🟢 Holat: faol\n"
        f"⏱ Qolgan vaqt: **{mins_left} daq {secs_left} sek**\n"
        f"💤 Harakatsizlik: {idle_min} daq (limit {BOT_SESSION_IDLE_MINUTES} daq)\n"
        f"📅 Ochilgan: {info['created_at'][:19].replace('T', ' ') if info['created_at'] else '-'}\n\n"
        "🚪 Chiqish: /logout"
    )


# =============== /PAROL (o'zgartirish) ===============
async def cmd_password(message: types.Message, state: FSMContext):
    """O'z parolini o'rnatish/o'zgartirish"""
    telegram_id = message.from_user.id

    if not bot_auth.is_bot_auth_enabled():
        await message.answer("ℹ️ Bot xavfsizlik rejimi o'chirilgan.")
        return

    with get_db_session() as db:
        employee = _find_employee_by_telegram(db, telegram_id)
        has_password = bot_auth.employee_has_password(db, employee)
        active_session = bot_auth.get_active_bot_session(db, telegram_id) is not None

    if not employee:
        await message.answer(
            "❌ Siz tizimda xodim sifatida ro'yxatdan o'tmagansiz.\n"
            "Admin bilan bog'laning."
        )
        return

    if not active_session and has_password:
        await message.answer(
            "🔐 Parolni o'zgartirish uchun avval tizimga kiring: /login"
        )
        return

    if has_password:
        await state.set_state(BotAuthStates.waiting_old_password)
        await message.answer(
            "🔐 **PAROLNI O'ZGARTIRISH**\n\n"
            "Avval JORIY parolingizni kiriting:"
        )
    else:
        await state.set_state(BotAuthStates.waiting_new_password)
        await message.answer(
            "🔐 **PAROL O'RNATISH**\n\n"
            "Yangi parolni kiriting (kamida 6 belgi):\n\n"
            "_Parolda harflar va raqamlar ishtirok etsin._"
        )


async def process_password_old(message: types.Message, state: FSMContext):
    """Parol o'zgartirish: joriy parolni tekshirish"""
    old_password = (message.text or "").strip()
    telegram_id = message.from_user.id
    await state.clear()

    with get_db_session() as db:
        employee = _find_employee_by_telegram(db, telegram_id)
        if employee is None:
            await message.answer("❌ Xodim topilmadi.")
            return
        if not bot_auth.verify_password(old_password, employee.password_hash):
            await message.answer("❌ Joriy parol noto'g'ri! Qayta urinib ko'ring: /parol")
            return

    await state.set_state(BotAuthStates.waiting_new_password)
    await message.answer("✅ To'g'ri. Endi YANGI parolni kiriting (kamida 6 belgi):")


async def process_password_new(message: types.Message, state: FSMContext):
    """Yangi parolni qabul qilish"""
    new_password = (message.text or "").strip()
    telegram_id = message.from_user.id

    if len(new_password) < 6:
        await message.answer("❌ Parol kamida 6 belgidan iborat bo'lishi kerak. Qayta kiriting:")
        return
    if new_password.lower() in ("123456", "password", "parol", "111111", "000000"):
        await message.answer("❌ Bu parol juda oddiy. Boshqa parol kiriting:")
        return

    await state.set_state(BotAuthStates.waiting_new_password_repeat)
    await state.update_data(new_password=new_password)
    await message.answer("🔁 Yangi parolni qayta kiriting (tasdiqlash uchun):")


async def process_password_repeat(message: types.Message, state: FSMContext):
    """Yangi parolni tasdiqlash va saqlash"""
    repeat = (message.text or "").strip()
    telegram_id = message.from_user.id
    data = await state.get_data()
    new_password = data.get("new_password", "")
    await state.clear()

    if repeat != new_password:
        await message.answer("❌ Parollar mos kelmadi. Qayta urinib ko'ring: /parol")
        return

    with get_db_session() as db:
        employee = _find_employee_by_telegram(db, telegram_id)
        if employee is None:
            await message.answer("❌ Xodim topilmadi.")
            return
        try:
            revoked = bot_auth.set_employee_bot_password(db, employee, new_password)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            return

    # Parol o'zgargach sessiyalar bekor qilinadi — qayta login talab qilamiz
    await message.answer(
        "✅ **PAROL YANGILANDI!**\n\n"
        f"🔓 Bekor qilingan sessiyalar: {revoked} ta\n\n"
        "🔐 Xavfsizlik uchun barcha sessiyalar yopildi.\n"
        "Yangi parol bilan qayta kiring: /login\n\n"
        "⚠️ Parolni hech kimga bermang. Web dashboardda ham shu parol ishlaydi."
    )


# =============== /CANCEL yordamchisi ===============
async def auth_cancel(message: types.Message, state: FSMContext):
    """Auth jarayonini bekor qilish"""
    current = await state.get_state()
    if current and current.startswith("BotAuthStates"):
        await state.clear()
        await message.answer("❌ Amal bekor qilindi. Kirish uchun: /login")
        return
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.")


# =============== REGISTER ===============
def register_handlers_bot_auth(dp: Dispatcher):
    """Auth handlerlarini ro'yxatdan o'tkazish"""
    dp.message.register(cmd_login, Command("login"))
    dp.message.register(cmd_login, F.text == "🔐 Kirish (login)")
    dp.message.register(cmd_logout, Command("logout"))
    dp.message.register(cmd_logout, F.text == "🚪 Chiqish (logout)")
    dp.message.register(cmd_session_status, Command("sessiya"))
    dp.message.register(cmd_session_status, F.text == "📊 Sessiya holati")
    dp.message.register(cmd_password, Command("parol"))
    dp.message.register(cmd_2fa, Command("2fa"))
    dp.message.register(cmd_2fa, F.text == "🔐 2FA (Google Authenticator)")

    # FSM bosqichlari
    dp.message.register(process_login_phone, BotAuthStates.waiting_phone)
    dp.message.register(process_login_password, BotAuthStates.waiting_password)
    dp.message.register(process_login_otp, BotAuthStates.waiting_otp)
    dp.message.register(process_password_old, BotAuthStates.waiting_old_password)
    dp.message.register(process_password_new, BotAuthStates.waiting_new_password)
    dp.message.register(process_password_repeat, BotAuthStates.waiting_new_password_repeat)
    dp.message.register(process_2fa_confirm, BotAuthStates.waiting_2fa_confirm)
    dp.message.register(process_2fa_disable, BotAuthStates.waiting_2fa_disable)

    # /cancel auth FSM'ni ham tozalashi uchun (start.py'dan OLDIN ro'yxatdan o'tadi)
    dp.message.register(auth_cancel, Command("cancel"))
