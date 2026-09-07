"""
Web Dashboard autentifikatsiya va ruxsatlar (v3)

- Xodimlar telefon raqami + parol bilan kiradi (parol PBKDF2 bilan saqlanadi)
- Muvaffaqiyatli kirishda HMAC bilan imzolangan stateless token beriladi
- Har bir /api endpoint'i rol matritsasiga (config.ROLES) ko'ra himoyalanadi

Birinchi marta ishga tushirish (parol o'rnatish):
    python -m dashboard.auth set-password --phone +998901234567 --password parol123

yoki .env da WEB_ADMIN_PASSWORD berilsa, paroli bo'lmagan barcha admin xodimlarga
avtomatik o'rnatiladi.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (  # noqa: E402
    BASE_DIR, ROLES, SECURITY_SETTINGS, get_role_label,
    role_can_edit, role_can_view, role_see_cost,
    SESSION_MINUTES, SESSION_IDLE_MINUTES,
)
from database import models  # noqa: E402
from database.session import get_db  # noqa: E402

# =============== SOZLAMALAR ===============
# Sessiya muddati (TZ: "5 minutdan 30 minutgacha sessiya saqlash"):
# access token SESSION_MINUTES (5..30 daqiqa) muddatga beriladi. Eski
# TOKEN_TTL_HOURS env'i o'rnatilgan bo'lsa, muvofiqlik uchun u ishlatiladi.
SESSION_TTL_SECONDS = SESSION_MINUTES * 60
SESSION_IDLE_SECONDS = SESSION_IDLE_MINUTES * 60
_hours_env = os.getenv("TOKEN_TTL_HOURS", "").strip()
if _hours_env:
    try:
        TOKEN_TTL_SECONDS = int(float(_hours_env) * 3600)
    except ValueError:
        TOKEN_TTL_SECONDS = SESSION_TTL_SECONDS
else:
    TOKEN_TTL_SECONDS = SESSION_TTL_SECONDS
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))
REFRESH_TOKEN_TTL_SECONDS = REFRESH_TOKEN_TTL_DAYS * 86400

# Sessiya bekor qilish sabablari (audit uchun)
SESSION_REVOKE_REASONS = ("logout", "expired", "idle_timeout", "admin", "password_change")
PASSWORD_MIN_LENGTH = int(os.getenv(
    "WEB_PASSWORD_MIN_LENGTH",
    str(SECURITY_SETTINGS.get("password_min_length", 8)),
))
_PBKDF2_ITERATIONS = 100_000
_SECRET_FILE = BASE_DIR / ".web_secret"


def _load_secret() -> str:
    """Token imzolash uchun maxfiy kalit — API_SECRET_KEY env yoki .web_secret fayl"""
    env_secret = os.getenv("API_SECRET_KEY", "").strip()
    if env_secret:
        return env_secret
    if _SECRET_FILE.exists():
        value = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    secret = secrets.token_hex(32)
    try:
        _SECRET_FILE.write_text(secret, encoding="utf-8")
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return secret


SECRET = _load_secret()
_bearer = HTTPBearer(auto_error=False)


# =============== PAROL ===============
def hash_password(password: str) -> str:
    """Parolni PBKDF2-HMAC-SHA256 bilan xeshlash"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Saqlangan xeshni tekshirish"""
    try:
        algo, iterations, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


# =============== TOKEN (HMAC imzolangan access + revoke qilish mumkin) ===============
def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("ascii") + b"==")


def _now() -> Any:
    """Vaqt — testlarda osongina surish uchun alohida funksiya"""
    from datetime import datetime
    return datetime.utcnow()


def _hash_refresh_token(refresh_token: str) -> str:
    """Refresh tokenni DB'da ochiq saqlamaslik uchun sha256 xeshi"""
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _issue_access_token(employee_id: int, session_id: Optional[int] = None) -> str:
    """Qisqa muddatli access token (sid — sessiya id, revoke tekshiruvi uchun)"""
    payload: Dict[str, Any] = {
        "uid": employee_id,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "iat": int(time.time()),
    }
    if session_id is not None:
        payload["sid"] = session_id
    body = _b64e(json.dumps(payload).encode("utf-8"))
    sig = hmac.new(SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def issue_token(employee_id: int) -> str:
    """Eski chaqiruvlar uchun sessiyasiz access token (backward-compat)"""
    return _issue_access_token(employee_id)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Tokenni tekshirib, payloadni qaytaradi (muddati o'tgan/yaroqsiz -> None)

    Xavfsizlik (v4): imzo base64 SATR sifatida qat'iyyat bilan solishtiriladi.
    Python b64 dekoderi padding '=' dan keyingi belgilarni e'tiborsiz qoldiradi,
    shuning uchun _b64d(sig) orqali solishtirish "token + 'x'" kabi o'zgartirilgan
    tokenni ham yaroqli deb qabul qilar edi. Qatorni to'g'ridan-to'g'ri qiyoslash
    har qanday o'zgartirishni rad etadi.
    """
    try:
        body, sig = token.split(".")
        expected_sig = _b64e(
            hmac.new(SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(_b64d(body).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, KeyError):
        return None


# =============== SESSEYALAR (refresh token, sliding, revoke) ===============
def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _session_is_active(session: "models.WebSession") -> bool:
    return session is not None and session.revoked_at is None and session.expires_at > _now()


def session_idle_seconds(session: "models.WebSession") -> Optional[int]:
    """Sessiya necha sekund harakatsiz turgani (last_seen_at bo'lmasa None)"""
    if session is None or session.last_seen_at is None:
        return None
    return max(0, int((_now() - session.last_seen_at).total_seconds()))


def session_is_idle_timed_out(session: "models.WebSession") -> bool:
    """Foydalanuvchi SESSION_IDLE_MINUTES dan ko'p harakatsiz turganmi"""
    idle = session_idle_seconds(session)
    return idle is not None and idle > SESSION_IDLE_SECONDS


def touch_session(db: Session, session: "models.WebSession") -> None:
    """Sessiya faolligini belgilash (harakatsizlik taymeri nolga tushadi).

    Har so'rovda DB'ga yozmaslik uchun faqat oxirgi yozuvdan 30+ sekund o'tgan
    bo'lsa yangilanadi — yetarli aniqlik, ortiqcha commit yo'q.
    """
    if session is None or session.revoked_at is not None:
        return
    now = _now()
    if session.last_seen_at is None or (now - session.last_seen_at).total_seconds() >= 30:
        session.last_seen_at = now
        try:
            db.commit()
        except Exception:
            db.rollback()


def session_to_dict(session: "models.WebSession") -> Dict[str, Any]:
    """Sessiya ma'lumotini ochiq (xavfsiz) dict ko'rinishiga o'tkazadi"""
    if session is None:
        return {}
    idle = session_idle_seconds(session)
    return {
        "id": session.id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
        "idle_seconds": idle,
        "idle_timeout_seconds": SESSION_IDLE_SECONDS,
        "is_revoked": session.revoked_at is not None,
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "revoke_reason": session.revoke_reason,
        "user_agent": session.user_agent,
    }


def create_web_session(db: Session, employee: models.Employee,
                       user_agent: str = "") -> Dict[str, Any]:
    """Login'da sessiya yaratadi: {access_token, refresh_token, session}

    Access token muddati — SESSION_MINUTES (5-30 daqiqa). Refresh token muddati
    REFRESH_TOKEN_TTL_DAYS (sliding), lekin harakatsizlik (SESSION_IDLE_MINUTES)
    yoki logout bo'lsa sessiya o'lgan bo'ladi.
    """
    from datetime import timedelta
    refresh_raw = _new_refresh_token()
    now = _now()
    session = models.WebSession(
        employee_id=employee.id,
        refresh_hash=_hash_refresh_token(refresh_raw),
        expires_at=now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS),
        last_seen_at=now,
        user_agent=(user_agent or "")[:250],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    access = _issue_access_token(employee.id, session_id=session.id)
    return {
        "access_token": access,
        "refresh_token": refresh_raw,
        "session": session,
        "expires_in": TOKEN_TTL_SECONDS,
    }


def refresh_session(db: Session, refresh_token: str) -> Optional[Dict[str, Any]]:
    """Refresh tokenni tekshirib yangi access+refresh beradi (sliding: muddat uzayadi).

    Eski refresh token aylantiriladi (rotatsiya) — qayta ishlatib bo'lmaydi.
    Qaytaradi: {access_token, refresh_token, session} yoki None.
    """
    from datetime import timedelta
    if not refresh_token:
        return None
    session = db.query(models.WebSession).filter(
        models.WebSession.refresh_hash == _hash_refresh_token(refresh_token)
    ).first()
    if not _session_is_active(session):
        return None
    # Harakatsizlik timeout'i: SESSION_IDLE_MINUTES dan ko'p jim tursa — sessiya o'ladi
    if session_is_idle_timed_out(session):
        revoke_session(db, session_id=session.id, reason="idle_timeout")
        return None
    # Sliding: muddatni hozirgi vaqtdan boshlab uzaytiramiz
    session.expires_at = _now() + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
    session.last_seen_at = _now()
    new_refresh = _new_refresh_token()
    session.refresh_hash = _hash_refresh_token(new_refresh)
    db.commit()
    db.refresh(session)
    access = _issue_access_token(session.employee_id, session_id=session.id)
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "session": session,
        "expires_in": TOKEN_TTL_SECONDS,
    }


def revoke_session(db: Session, session_id: int = None,
                   refresh_token: str = None,
                   reason: str = "logout") -> bool:
    """Sessiyani revoke qiladi (logout/expired/admin) — access ham refresh ham ishlamay qoladi.

    Sessiya o'lganda o'sha sessiya orqali berilgan barcha darajalar (ruxsatlar)
    amal qilmas bo'ladi: get_current_user sid tekshiruvi 401 qaytaradi.
    """
    query = db.query(models.WebSession)
    if session_id is not None:
        query = query.filter(models.WebSession.id == session_id)
    elif refresh_token:
        query = query.filter(
            models.WebSession.refresh_hash == _hash_refresh_token(refresh_token)
        )
    else:
        return False
    session = query.first()
    if session is None:
        return False
    if session.revoked_at is None:
        session.revoked_at = _now()
    session.revoke_reason = (reason or "logout")[:30]
    db.commit()
    return True


def revoke_all_employee_sessions(db: Session, employee_id: int,
                                 reason: str = "admin") -> int:
    """Xodimning barcha faol web sessiyalarini bekor qiladi (masalan parol o'zgarsa)"""
    sessions = db.query(models.WebSession).filter(
        models.WebSession.employee_id == employee_id,
        models.WebSession.revoked_at.is_(None),
    ).all()
    now = _now()
    for s in sessions:
        s.revoked_at = now
        s.revoke_reason = (reason or "admin")[:30]
    if sessions:
        db.commit()
    return len(sessions)


# =============== FOYDALANUVCHI ===============
def normalize_phone_digits(phone: Optional[str]) -> str:
    """Telefon raqamini taqqoslash uchun raqamlarga aylantiradi"""
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def find_employee_by_phone(db: Session, phone: str) -> Optional[models.Employee]:
    """Telefon raqami bo'yicha xodimni topish (formatdan qat'iy nazar)"""
    digits = normalize_phone_digits(phone)
    if not digits:
        return None
    for emp in db.query(models.Employee).all():
        if normalize_phone_digits(emp.phone_number) == digits:
            return emp
    return None


def effective_role(employee: models.Employee) -> str:
    """Xodimning amaldagi roli (is_admin -> direktor)"""
    if employee.is_admin:
        return "direktor"
    return employee.role if (employee.role or "") in ROLES else "ishchi"


def user_to_dict(employee: models.Employee) -> Dict[str, Any]:
    """Xodimni /api/me uchun ochiq dict'ga aylantiradi (ruxsatlar bilan)"""
    role = effective_role(employee)
    return {
        "id": employee.id,
        "full_name": employee.full_name,
        "phone": employee.phone_number,
        "telegram_id": employee.telegram_id,
        "role": role,
        "role_label": get_role_label(role),
        "is_admin": bool(employee.is_admin),
        "has_password": bool(employee.password_hash),
        "permissions": {
            "can_view": list(ROLES[role]["can_view"]),
            "can_edit": list(ROLES[role]["can_edit"]),
            "see_cost": role_see_cost(role),
            "discount_limit": ROLES[role].get("discount_limit", 0),
        },
    }


class AuthUser:
    """Tasdiqlangan foydalanuvchi — endpoint larga Depends orqali beriladi"""

    def __init__(self, employee: models.Employee):
        self.id = employee.id
        self.full_name = employee.full_name
        self.phone = employee.phone_number
        self.telegram_id = employee.telegram_id
        self.is_admin = bool(employee.is_admin)
        self.role = effective_role(employee)
        self.see_cost = role_see_cost(self.role)
        self._employee = employee

    def to_dict(self) -> Dict[str, Any]:
        return user_to_dict(self._employee)


# =============== TANNARX MAYDONLARI FILTRI (see_cost=False) ===============
# Rol matritsasida see_cost=False bo'lgan rollar (sotuvchi, kassir, omborchi,
# haydovchi, ishchi) tannarx/narx ma'lumotlarini API'dan olmasligi kerak.
# Bu filtr server tomonda qo'llaniladi — frontend'da yashirish yetarli emas.
COST_FIELD_KEYS = frozenset({
    "price_per_unit",   # xom ashyo / qabul akti birlik tannarxi
    "production_cost",  # mahsulot tannarxi
    "profit_margin",    # tannarxdan kelib chiqqan marja
    "total_cost",       # ishlab chiqarish buyurtmasi tannarxi
    "warehouse_value",  # ombor umumiy qiymati (tannarx asosida)
    "value",            # xom ashyo qoldig'i qiymati (qoldiq * tannarx)
})


def strip_cost_fields(data, user: AuthUser) -> Any:
    """user.see_cost=False bo'lsa, JSON javobdan tannarx maydonlarini olib tashlaydi.

    Dict/list ichida rekursiv ishlaydi — hech qanday chuqurlikdagi tannarx maydoni
    qolib ketmaydi.
    """
    if getattr(user, "see_cost", True):
        return data
    if isinstance(data, dict):
        return {k: strip_cost_fields(v, user) for k, v in data.items()
                if k not in COST_FIELD_KEYS}
    if isinstance(data, list):
        return [strip_cost_fields(item, user) for item in data]
    return data


def _unauthorized(detail: str = "Avtorizatsiya talab qilinadi (token yo'q yoki yaroqsiz)"):
    return HTTPException(status_code=401, detail=detail)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
    request: Request = None,
) -> AuthUser:
    """Bearer tokenni tekshiradi va xodimni DB'dan yuklaydi.

    Access token tarkibidagi sid (sessiya) revoke qilingan bo'lsa -> 401,
    shuning uchun logout'dan keyin eski token ham ishlamaydi.
    Sessiya SESSION_IDLE_MINUTES dan ko'p harakatsiz tursa ham 401 bo'ladi
    va sessiya "idle_timeout" sababi bilan bekor qilinadi — foydalanuvchi
    qayta login qilib darajalarni yangidan oladi.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    payload = decode_token(credentials.credentials)
    if not payload:
        raise _unauthorized()
    sid = payload.get("sid")
    web_session = None
    if sid is not None:
        web_session = db.query(models.WebSession).filter(
            models.WebSession.id == sid
        ).first()
        if web_session is None or web_session.revoked_at is not None:
            raise _unauthorized("Sessiya bekor qilingan (logout)")
        if session_is_idle_timed_out(web_session):
            revoke_session(db, session_id=sid, reason="idle_timeout")
            raise _unauthorized("Sessiya harakatsizlik tufayli tugadi. Qayta kiring.")
    employee = db.query(models.Employee).filter(
        models.Employee.id == payload.get("uid")
    ).first()
    if not employee:
        raise _unauthorized("Xodim topilmadi")
    if web_session is not None:
        touch_session(db, web_session)
    user = AuthUser(employee)
    if request is not None:
        # Javob filtri (tannarx maydonlarini yashirish) uchun joriy foydalanuvchini saqlaymiz
        request.state.auth_user = user
    return user


# =============== HTML SAHIFA AUTH (legacy root dashboard) ===============
WEB_TOKEN_COOKIE = "web_token"


def get_web_user(request: Request, db: Session) -> Optional[AuthUser]:
    """HTML sahifalar (root dashboard) uchun foydalanuvchini aniqlash.

    Avval web_token cookie'sini, bo'lmasa Authorization: Bearer header'ini tekshiradi.
    Kirgan foydalanuvchi topilmasa -> None (sahifa login'ga yo'naltiriladi).
    Harakatsizlik timeout'i bo'lsa sessiya bekor qilib None qaytaradi.
    """
    token = (request.cookies or {}).get(WEB_TOKEN_COOKIE, "") or ""
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    sid = payload.get("sid")
    web_session = None
    if sid is not None:
        web_session = db.query(models.WebSession).filter(
            models.WebSession.id == sid
        ).first()
        if web_session is None or web_session.revoked_at is not None:
            return None
        if session_is_idle_timed_out(web_session):
            revoke_session(db, session_id=sid, reason="idle_timeout")
            return None
    employee = db.query(models.Employee).filter(
        models.Employee.id == payload.get("uid")
    ).first()
    if not employee:
        return None
    if web_session is not None:
        touch_session(db, web_session)
    return AuthUser(employee)


def require_role(module: str, edit: bool = False):
    """Rol matritsasi bo'yicha modulga kirishni tekshiruvchi dependency"""
    def dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        ok = (role_can_edit if edit else role_can_view)(user.role, module)
        if not ok:
            raise HTTPException(
                status_code=403,
                detail=f"Ruxsat yo'q: '{module}' bo'limi sizning rolingizga ({get_role_label(user.role)}) ochiq emas.",
            )
        return user
    return dep


def require_any_edit(modules: List[str]):
    """Kamida bitta modulda tahrirlash huquqini talab qiluvchi dependency"""
    def dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not any(role_can_edit(user.role, m) for m in modules):
            raise HTTPException(
                status_code=403,
                detail=f"Ruxsat yo'q: bu amal uchun ({', '.join(modules)}) huquqlaridan biri kerak.",
            )
        return user
    return dep


def set_employee_password(db: Session, employee: models.Employee, password: str):
    """Xodim parolini o'rnatish (validatsiya bilan).

    Xavfsizlik: parol o'zgarsa xodimning BARCHA web sessiyalari bekor qilinadi —
    eski tokenga berilgan darajalar amal qilmas bo'ladi.
    v4: Bot sessiyalari ham bekor qilinadi — bot'da qayta /login talab qilinadi.
    """
    if len(password or "") < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Parol kamida {PASSWORD_MIN_LENGTH} belgidan iborat bo'lishi kerak"
        )
    employee.password_hash = hash_password(password)
    try:
        revoke_all_employee_sessions(db, employee.id, reason="password_change")
    except Exception:
        db.rollback()
    # v4: Bot sessiyalarini ham bekor qilish (utils/bot_auth.py)
    try:
        from utils.bot_auth import revoke_all_employee_bot_sessions
        revoke_all_employee_bot_sessions(db, employee.id, reason="password_change")
    except Exception:
        pass
    db.commit()


def bootstrap_admin_passwords() -> int:
    """.env'dagi WEB_ADMIN_PASSWORD paroli bo'lmagan admin xodimlarga o'rnatiladi"""
    default_password = os.getenv("WEB_ADMIN_PASSWORD", "").strip()
    if not default_password:
        return 0
    if len(default_password) < PASSWORD_MIN_LENGTH:
        print(f"⚠️ WEB_ADMIN_PASSWORD juda qisqa (min {PASSWORD_MIN_LENGTH}) — o'tkazib yuborildi")
        return 0
    from database.session import get_db_session
    db = get_db_session()
    try:
        admins = db.query(models.Employee).filter(models.Employee.is_admin == True).all()
        count = 0
        for emp in admins:
            if not emp.password_hash:
                emp.password_hash = hash_password(default_password)
                count += 1
        if count:
            db.commit()
    finally:
        db.close()
    return count


# =============== CLI ===============
def _cli():
    parser = argparse.ArgumentParser(prog="dashboard.auth", description="Web dashboard parol boshqaruvi")
    sub = parser.add_subparsers(dest="command", required=True)

    p_set = sub.add_parser("set-password", help="Xodim parolini o'rnatish")
    p_set.add_argument("--phone", required=True, help="Xodim telefon raqami, masalan +998901234567")
    p_set.add_argument("--password", required=True, help="Yangi parol")

    p_list = sub.add_parser("list-users", help="Xodimlar va parol holati")
    args = parser.parse_args()

    from database.session import get_db_session
    db = get_db_session()
    try:
        if args.command == "set-password":
            emp = find_employee_by_phone(db, args.phone)
            if not emp:
                print(f"❌ {args.phone} raqamli xodim topilmadi")
                sys.exit(1)
            try:
                set_employee_password(db, emp, args.password)
            except ValueError as e:
                print(f"❌ {e}")
                sys.exit(1)
            print(f"✅ {emp.full_name} uchun parol o'rnatildi (rol: {effective_role(emp)})")
        elif args.command == "list-users":
            for emp in db.query(models.Employee).order_by(models.Employee.full_name).all():
                pwd = "✅" if emp.password_hash else "❌ yo'q"
                print(f"{emp.full_name:30s} {emp.phone_number:16s} rol={effective_role(emp):12s} parol:{pwd}")
    finally:
        db.close()


if __name__ == "__main__":
    _cli()
