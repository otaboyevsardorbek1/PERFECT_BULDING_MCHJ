"""
Bot xavfsizlik moduli — LOGIN/PAROL + SESSIYA (v4)

TZ talablarini amalga oshiradi:
- Har bir xodim botda parol bilan tasdiqlanadi (PBKDF2 xesh, web auth bilan bir xil format)
- Muvaffaqiyatli login 5-30 daqiqa (BOT_SESSION_MINUTES) sessiya beradi
- Sessiya tugaganda (muddat / harakatsizlik) yoki /logout qilinganda
  xodimga berilgan BARCHA darajalar (rol ruxsatlari) avtomatik bekor bo'ladi
- Parolni xato kiritishda vaqtincha bloklash (bruteforce himoyasi)
- Parol o'zgarsa barcha faol sessiyalar bekor qilinadi (web + bot)

Muhim: mavjud tizimga ziyon yetkazmaslik uchun BOT_AUTH_ENABLED=false
bo'lsa eski holat (telegram_id bo'yicha ruxsat) saqlanadi.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from config import (
    ADMIN_IDS,
    BOT_AUTH_ENABLED,
    BOT_SESSION_MINUTES,
    BOT_SESSION_IDLE_MINUTES,
    BOT_LOGIN_MAX_ATTEMPTS,
    BOT_LOGIN_LOCKOUT_MINUTES,
    BOT_MAX_SESSIONS_PER_EMPLOYEE,
)

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 100_000  # dashboard/auth.py bilan bir xil
_REVOKE_REASONS = ("logout", "expired", "idle_timeout", "admin", "password_change")

# Xato parol sanog'i: {telegram_id: {"count": int, "locked_until": datetime|None}}
_login_attempts: Dict[int, Dict[str, Any]] = {}


# =============== PAROL (dashboard/auth.py formatida) ===============
def hash_password(password: str) -> str:
    """Parolni PBKDF2-HMAC-SHA256 bilan xeshlash (web auth bilan mos)"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Saqlangan xeshni tekshirish (web auth bilan mos)"""
    try:
        algo, iterations, salt, expected = (stored or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


# =============== 2FA (Google Authenticator / TOTP) ===============
def employee_2fa_enabled(employee) -> bool:
    """Xodimda 2FA yoqilganmi (bot login'da ham talab qilinadi)"""
    return bool(getattr(employee, "otp_enabled", False) and getattr(employee, "otp_secret", None))


def verify_2fa_code(employee, code: str) -> bool:
    """Google Authenticator kodini tekshirish"""
    if not employee_2fa_enabled(employee):
        return False
    from utils.totp import verify_totp
    return verify_totp(employee.otp_secret, code)


# =============== BRUTEFORCE HIMOYASI ===============
def _attempts_key(telegram_id: int) -> Dict[str, Any]:
    return _login_attempts.setdefault(
        telegram_id, {"count": 0, "locked_until": None}
    )


def is_login_locked(telegram_id: int) -> Optional[int]:
    """Foydalanuvchi bloklangan bo'lsa — qolgan sekundni, aks holda None qaytaradi"""
    if not _login_attempts:
        return None
    info = _attempts_key(telegram_id)
    locked_until = info.get("locked_until")
    if not locked_until:
        return None
    remaining = (locked_until - datetime.utcnow()).total_seconds()
    if remaining <= 0:
        # Blok muddati tugadi — hisobni tozalash
        info["count"] = 0
        info["locked_until"] = None
        return None
    return int(remaining) + 1


def register_failed_login(telegram_id: int) -> int:
    """Xato parolni qayd etadi; limitdan o'sa — blok qo'yadi. Qolgan urinishlar sonini qaytaradi."""
    info = _attempts_key(telegram_id)
    info["count"] = int(info.get("count", 0)) + 1
    if info["count"] >= BOT_LOGIN_MAX_ATTEMPTS:
        info["locked_until"] = datetime.utcnow() + timedelta(
            minutes=BOT_LOGIN_LOCKOUT_MINUTES
        )
        logger.warning(
            f"Bot login: {telegram_id} {BOT_LOGIN_LOCKOUT_MINUTES} daqiqaga bloklandi "
            f"({info['count']} marta xato parol)"
        )
        return 0
    return BOT_LOGIN_MAX_ATTEMPTS - info["count"]


def reset_login_attempts(telegram_id: int) -> None:
    """Muvaffaqiyatli login'dan keyin hisobni tozalash"""
    _attempts_key(telegram_id)["count"] = 0
    _attempts_key(telegram_id)["locked_until"] = None


# =============== PAROL HOLATI ===============
def employee_has_password(db, employee) -> bool:
    """Xodimda parol bormi"""
    return bool(employee is not None and employee.password_hash)


def claim_employee_telegram(db, employee, telegram_id: int) -> bool:
    """Bo'sh telegram maydonini birinchi login urinishida bog'lash.

    Birinchi marta kirish oqimi (parol hali o'rnatilmagan xodim) shu yordamchi
    orqali telegram ID'ni bog'laydi — aks holda foydalanuvchi "parolni /parol
    bilan o'rnatib oling" deb yo'naltiriladi, lekin /parol xodimni telegram_id
    orqali topadi va bog'lanmagan hisob uchun bu DOIM muvaffaqiyatsiz tugaydi
    (bootstrap deadlock). Telefon raqamini bilish login oqimi allaqachon
    identifikatsiya sifatida ishlatiladi, shuning uchun xavfsizlik darajasi
    bir xil qoladi. Bog'langan bo'lsa boshqa hisobga o'tkazilmaydi.

    Qaytaradi: bog'landi/allaqachon shu hisobda -> True, band -> False.
    """
    if employee is None:
        return False
    if employee.telegram_id == telegram_id:
        return True
    if employee.telegram_id is None:
        employee.telegram_id = telegram_id
        db.commit()
        logger.info(
            f"Telegram ID bog'landi: employee_id={employee.id} -> {telegram_id}"
        )
        return True
    return False


def set_employee_bot_password(db, employee, password: str, min_length: int = 6) -> int:
    """Xodim parolini o'rnatadi va barcha faol sessiyalarni (bot) bekor qiladi.

    Qaytaradi: bekor qilingan sessiyalar soni.
    Web dashboard paroli bilan BIR XIL maydon (Employee.password_hash) ishlatiladi —
    bir marta o'rnatilgan parol ham web, ham bot uchun ishlaydi.
    """
    if not password or len(password) < min_length:
        raise ValueError(f"Parol kamida {min_length} belgidan iborat bo'lishi kerak")
    employee.password_hash = hash_password(password)
    revoked = revoke_all_employee_bot_sessions(db, employee.id, reason="password_change")
    db.commit()
    logger.info(f"Parol o'rnatildi: employee_id={employee.id}, {revoked} sessiya bekor qilindi")
    return revoked


# =============== SESSIYA AMALLARI ===============
def create_bot_session(db, employee, telegram_id: int) -> Any:
    """Yangi bot sessiyasi yaratadi (eski faol sessiyalarni yopib).

    TZ: "5 minutdan 30 minutgacha sessiya saqlash" — muddat BOT_SESSION_MINUTES.
    """
    from database import models

    now = datetime.utcnow()
    # Avvalgi faol sessiyalarni yopish (bir telegram + bir xodim = bitta faol sessiya)
    db.query(models.EmployeeAuthSession).filter(
        models.EmployeeAuthSession.telegram_id == telegram_id,
        models.EmployeeAuthSession.revoked_at.is_(None),
    ).update(
        {
            "revoked_at": now,
            "revoke_reason": "expired",
        }
    )
    session = models.EmployeeAuthSession(
        employee_id=employee.id,
        telegram_id=telegram_id,
        created_at=now,
        expires_at=now + timedelta(minutes=BOT_SESSION_MINUTES),
        last_activity=now,
    )
    db.add(session)

    # Xodim bo'yicha eski sessiyalar soni limitdan oshsa, eng eskilarini yopish
    old = (
        db.query(models.EmployeeAuthSession)
        .filter(
            models.EmployeeAuthSession.employee_id == employee.id,
            models.EmployeeAuthSession.revoked_at.is_(None),
        )
        .order_by(models.EmployeeAuthSession.created_at.asc())
        .all()
    )
    excess = len(old) - BOT_MAX_SESSIONS_PER_EMPLOYEE
    if excess > 0:
        for s in old[:excess]:
            s.revoked_at = now
            s.revoke_reason = "expired"

    db.commit()
    db.refresh(session)
    return session


def _session_expired(session) -> bool:
    return session.expires_at <= datetime.utcnow()


def _session_idle_timed_out(session) -> bool:
    if session.last_activity is None:
        return False
    idle = (datetime.utcnow() - session.last_activity).total_seconds()
    return idle > BOT_SESSION_IDLE_MINUTES * 60


def get_active_bot_session(db, telegram_id: int):
    """Foydalanuvchi joriy faol (yaroqli) sessiyasini qaytaradi.

    Sessiya muddati tugagan yoki harakatsizlikdan o'lgan bo'lsa — uni
    avtomatik bekor qilib (revoke) None qaytaradi: darajalar bekor bo'ladi.
    """
    from database import models

    session = (
        db.query(models.EmployeeAuthSession)
        .filter(
            models.EmployeeAuthSession.telegram_id == telegram_id,
            models.EmployeeAuthSession.revoked_at.is_(None),
        )
        .order_by(models.EmployeeAuthSession.created_at.desc())
        .first()
    )
    if session is None:
        return None
    if _session_expired(session):
        session.revoked_at = datetime.utcnow()
        session.revoke_reason = "expired"
        db.commit()
        return None
    if _session_idle_timed_out(session):
        session.revoked_at = datetime.utcnow()
        session.revoke_reason = "idle_timeout"
        db.commit()
        return None
    return session


def touch_bot_session(db, session) -> None:
    """Sessiya faolligini yangilaydi (idle taymerini nolga tushiradi).

    DB'ga ortiqcha yozmaslik uchun oxirgi yozuvdan 30+ sekund o'tgan bo'lsa yangilanadi.
    """
    if session is None or session.revoked_at is not None:
        return
    now = datetime.utcnow()
    if session.last_activity is None or (now - session.last_activity).total_seconds() >= 30:
        session.last_activity = now
        try:
            db.commit()
        except Exception:
            db.rollback()


def logout_bot_session(db, telegram_id: int) -> bool:
    """Foydalanuvchi /logout: faol sessiyani bekor qiladi — barcha darajalar bekor bo'ladi."""
    from database import models

    now = datetime.utcnow()
    sessions = (
        db.query(models.EmployeeAuthSession)
        .filter(
            models.EmployeeAuthSession.telegram_id == telegram_id,
            models.EmployeeAuthSession.revoked_at.is_(None),
        )
        .all()
    )
    for s in sessions:
        s.revoked_at = now
        s.revoke_reason = "logout"
        s.logout_at = now
    if sessions:
        db.commit()
    return bool(sessions)


def revoke_all_employee_bot_sessions(db, employee_id: int, reason: str = "admin") -> int:
    """Xodimning BARCHA faol bot sessiyalarini bekor qiladi (parol o'zgarsa / admin buyrug'i)."""
    from database import models

    now = datetime.utcnow()
    sessions = (
        db.query(models.EmployeeAuthSession)
        .filter(
            models.EmployeeAuthSession.employee_id == employee_id,
            models.EmployeeAuthSession.revoked_at.is_(None),
        )
        .all()
    )
    for s in sessions:
        s.revoked_at = now
        s.revoke_reason = (reason or "admin")[:30]
    if sessions:
        db.commit()
    return len(sessions)


def revoke_employee_bot_sessions_by_telegram_id(db, telegram_id: int, reason: str = "admin") -> int:
    """Telegram ID bo'yicha sessiyalarni bekor qilish (admin paneli uchun)"""
    from database import models

    now = datetime.utcnow()
    sessions = (
        db.query(models.EmployeeAuthSession)
        .filter(
            models.EmployeeAuthSession.telegram_id == telegram_id,
            models.EmployeeAuthSession.revoked_at.is_(None),
        )
        .all()
    )
    for s in sessions:
        s.revoked_at = now
        s.revoke_reason = (reason or "admin")[:30]
    if sessions:
        db.commit()
    return len(sessions)


def session_to_dict(session) -> Dict[str, Any]:
    """Sessiyani xavfsiz (parolsiz) dict ko'rinishiga o'tkazadi"""
    if session is None:
        return {}
    now = datetime.utcnow()
    return {
        "id": session.id,
        "employee_id": session.employee_id,
        "telegram_id": session.telegram_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "last_activity": session.last_activity.isoformat() if session.last_activity else None,
        "seconds_left": max(0, int((session.expires_at - now).total_seconds()))
        if session.expires_at
        else 0,
        "idle_seconds": max(0, int((now - session.last_activity).total_seconds()))
        if session.last_activity
        else None,
        "idle_timeout_seconds": BOT_SESSION_IDLE_MINUTES * 60,
        "is_revoked": session.revoked_at is not None,
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "revoke_reason": session.revoke_reason,
    }


def cleanup_expired_sessions(db, max_age_hours: int = 168) -> int:
    """Eski yopilgan sessiya yozuvlarini tozalash (default: 7 kundan eski)."""
    from database import models

    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    deleted = (
        db.query(models.EmployeeAuthSession)
        .filter(
            models.EmployeeAuthSession.revoked_at.isnot(None),
            models.EmployeeAuthSession.revoked_at < cutoff,
        )
        .delete()
    )
    if deleted:
        db.commit()
    return deleted


# =============== RUXSAT QATLAMI (access.py bilan integratsiya) ===============
def is_bot_auth_enabled() -> bool:
    """Bot parol talabi yoqilganmi (eski tizimni saqlab qolish uchun o'chirish mumkin)"""
    return BOT_AUTH_ENABLED


def check_session_permission(db, telegram_id: int) -> Optional[str]:
    """Sessiya holatini tekshiradi.

    Qaytaradi:
      None          — hammasi joyida (yoki parol talabi o'chirilgan)
      "no_session"  — sessiya yo'q/yoki o'lgan -> /login kerak
    """
    if not is_bot_auth_enabled():
        return None
    # Eski tizim uzluksizligi: ADMIN_IDS'dagi superuser xodim yozuviga bog'lanmagan
    # bo'lsa, uni bloklamaymiz (login qilishga imkon yo'q bo'lardi). Xodim yozuvi
    # mavjud bo'lsa — admin ham oddiy xodim kabi sessiya o'tkazadi.
    if telegram_id in ADMIN_IDS:
        from database import models
        linked = (
            db.query(models.Employee.id)
            .filter(models.Employee.telegram_id == telegram_id)
            .first()
        )
        if linked is None:
            return None
    session = get_active_bot_session(db, telegram_id)
    if session is None:
        return "no_session"
    touch_bot_session(db, session)
    return None
