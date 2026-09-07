"""v4 bot auth modulining smoke testlari (import + asosiy logika)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("BOT_TOKEN", "test_token_1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ")
os.environ.setdefault("ADMIN_IDS", "123456789")
os.environ.setdefault("SQLITE_DB_PATH", "/tmp/test_bot_auth_smoke.db")

from datetime import datetime, timedelta


def test_imports():
    from utils import bot_auth
    from utils.access import session_is_valid, ensure_access, get_user_role
    import handlers.bot_auth
    assert hasattr(bot_auth, "create_bot_session")
    assert hasattr(bot_auth, "logout_bot_session")
    assert hasattr(bot_auth, "check_session_permission")
    assert hasattr(handlers.bot_auth, "register_handlers_bot_auth")


def test_password_hash_roundtrip():
    from utils.bot_auth import hash_password, verify_password
    stored = hash_password("parol123")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("parol123", stored)
    assert not verify_password("xato", stored)
    assert not verify_password("parol123", None)
    assert not verify_password("parol123", "")


def test_login_lockout_logic():
    from utils import bot_auth
    bot_auth._login_attempts.clear()
    tg_id = 999001
    # Bloklanmagan holat
    assert bot_auth.is_login_locked(tg_id) is None
    # 1-marta xato (limit 3) — 2 urinish qoladi
    assert bot_auth.register_failed_login(tg_id) == 2
    assert bot_auth.is_login_locked(tg_id) is None
    # 2-marta — 1 urinish qoladi, hali blok yo'q
    assert bot_auth.register_failed_login(tg_id) == 1
    assert bot_auth.is_login_locked(tg_id) is None
    # 3-marta — blok
    assert bot_auth.register_failed_login(tg_id) == 0
    remaining = bot_auth.is_login_locked(tg_id)
    assert remaining is not None and remaining > 0
    # Reset
    bot_auth.reset_login_attempts(tg_id)
    assert bot_auth.is_login_locked(tg_id) is None
    bot_auth._login_attempts.clear()


def test_session_lifecycle(db_session):
    from database import models
    from utils import bot_auth

    emp = models.Employee(
        full_name="Sessiya Test", phone_number="+998909999999",
        position="Ishchi", department="Test",
        hire_date=datetime.utcnow(), salary=0,
        role="sotuvchi", password_hash=bot_auth.hash_password("parol123"),
    )
    db_session.add(emp)
    db_session.commit()

    # Parol tekshiruvi
    assert bot_auth.employee_has_password(db_session, emp)
    assert bot_auth.verify_password("parol123", emp.password_hash)

    # Sessiya yaratish
    s = bot_auth.create_bot_session(db_session, emp, telegram_id=777001)
    assert s.id is not None
    assert s.expires_at > datetime.utcnow()
    assert (s.expires_at - s.created_at).total_seconds() <= bot_auth.BOT_SESSION_MINUTES * 60 + 1

    # Faol sessiya topiladi
    active = bot_auth.get_active_bot_session(db_session, 777001)
    assert active is not None and active.id == s.id
    assert bot_auth.check_session_permission(db_session, 777001) is None

    # Logout — darajalar bekor bo'ladi
    assert bot_auth.logout_bot_session(db_session, 777001) is True
    assert bot_auth.get_active_bot_session(db_session, 777001) is None
    assert bot_auth.check_session_permission(db_session, 777001) == "no_session"


def test_session_expiry_and_idle(db_session):
    from database import models
    from utils import bot_auth

    emp = models.Employee(
        full_name="Expiry Test", phone_number="+998909999998",
        position="Ishchi", department="Test",
        hire_date=datetime.utcnow(), salary=0, role="ishchi",
        password_hash=bot_auth.hash_password("parol123"),
    )
    db_session.add(emp)
    db_session.commit()

    # Muddati tugagan sessiya
    s1 = models.EmployeeAuthSession(
        employee_id=emp.id, telegram_id=777002,
        created_at=datetime.utcnow() - timedelta(minutes=60),
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        last_activity=datetime.utcnow() - timedelta(minutes=2),
    )
    db_session.add(s1)
    db_session.commit()
    assert bot_auth.get_active_bot_session(db_session, 777002) is None
    # Avtomatik revoke qilingan
    db_session.refresh(s1)
    assert s1.revoked_at is not None and s1.revoke_reason == "expired"

    # Idle timeout sessiyasi
    from config import BOT_SESSION_IDLE_MINUTES as BOT_IDLE
    s2 = models.EmployeeAuthSession(
        employee_id=emp.id, telegram_id=777003,
        created_at=datetime.utcnow() - timedelta(minutes=10),
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        last_activity=datetime.utcnow() - timedelta(minutes=BOT_IDLE + 1),
    )
    db_session.add(s2)
    db_session.commit()
    assert bot_auth.get_active_bot_session(db_session, 777003) is None
    db_session.refresh(s2)
    assert s2.revoke_reason == "idle_timeout"


def test_set_password_revokes_sessions(db_session):
    from database import models
    from utils import bot_auth

    emp = models.Employee(
        full_name="Revoke Test", phone_number="+998909999997",
        position="Ishchi", department="Test",
        hire_date=datetime.utcnow(), salary=0, role="kassir",
    )
    db_session.add(emp)
    db_session.commit()

    bot_auth.set_employee_bot_password(db_session, emp, "birinchi123")
    s = bot_auth.create_bot_session(db_session, emp, telegram_id=777004)
    assert bot_auth.get_active_bot_session(db_session, 777004) is not None

    # Parol o'zgarsa sessiya bekor bo'ladi
    revoked = bot_auth.set_employee_bot_password(db_session, emp, "ikkinchi123")
    assert revoked >= 1
    assert bot_auth.get_active_bot_session(db_session, 777004) is None
    # Yangi parol ishlaydi
    assert bot_auth.verify_password("ikkinchi123", emp.password_hash)


def test_admin_bypass_and_session_free_commands(db_session):
    """Login oldi komandalar sessiyasiz ham yaroqli hisoblanadi"""
    from utils.access import session_is_valid
    assert session_is_valid(db_session, 424242, "/start") is True
    assert session_is_valid(db_session, 424242, "/login") is True
    assert session_is_valid(db_session, 424242, "/help") is True
    assert session_is_valid(db_session, 424242, "/cancel") is True
    assert session_is_valid(db_session, 424242, "🔐 Kirish (login)") is True
    assert session_is_valid(db_session, 424242, "/sessiya") is True
    assert session_is_valid(db_session, 424242, "/parol") is True
    assert session_is_valid(db_session, 424242, "/logout") is True
    # Sessiyasiz oddiy buyruq — BOT_AUTH_ENABLED=true bo'lsa yaroqsiz
    from utils import bot_auth
    if bot_auth.is_bot_auth_enabled():
        assert session_is_valid(db_session, 424242, "📦 Ombor holati") is False


def test_web_password_compat(db_session):
    """Bot hash'lash web auth (dashboard/auth.py) bilan mos bo'lishi kerak"""
    from database import models
    from utils.bot_auth import hash_password
    from dashboard.auth import verify_password as web_verify

    emp = models.Employee(
        full_name="Web Compat", phone_number="+998909999996",
        position="Ishchi", department="Test",
        hire_date=datetime.utcnow(), salary=0, role="ishchi",
    )
    db_session.add(emp)
    db_session.commit()
    emp.password_hash = hash_password("mos_parol1")
    db_session.commit()
    assert web_verify("mos_parol1", emp.password_hash)
    assert not web_verify("boshqa", emp.password_hash)


def test_session_to_dict_no_secrets():
    from utils.bot_auth import session_to_dict
    d = session_to_dict(None)
    assert d == {}


def test_cleanup_expired(db_session):
    from database import models
    from utils import bot_auth
    emp = models.Employee(
        full_name="Cleanup Test", phone_number="+998909999995",
        position="Ishchi", department="Test",
        hire_date=datetime.utcnow(), salary=0, role="ishchi",
    )
    db_session.add(emp)
    db_session.commit()
    old = models.EmployeeAuthSession(
        employee_id=emp.id, telegram_id=777005,
        created_at=datetime.utcnow() - timedelta(days=30),
        expires_at=datetime.utcnow() - timedelta(days=29),
        last_activity=datetime.utcnow() - timedelta(days=30),
        revoked_at=datetime.utcnow() - timedelta(days=29),
        revoke_reason="logout",
    )
    db_session.add(old)
    db_session.commit()
    deleted = bot_auth.cleanup_expired_sessions(db_session, max_age_hours=24 * 7)
    assert deleted >= 1


def test_is_session_free_text_matrix():
    """Middleware va session_is_valid bitta yordamchidan foydalanadi:
    /buyruq shakli VA to'liq menyu tugma matni ikkalasi ham ochiq bo'lishi kerak"""
    from utils.access import is_session_free_text
    # Buyruqlar
    assert is_session_free_text("/start")
    assert is_session_free_text("/login")
    assert is_session_free_text("/login@my_bot")      # bot username bilan
    assert is_session_free_text("/LOGIN")             # katta-kichik harf
    assert is_session_free_text("  /login  ")          # atrofdagi bo'shliqlar
    assert is_session_free_text("/parol")
    assert is_session_free_text("/sessiya")
    assert is_session_free_text("/logout")
    # Reply keyboard tugmalari (to'liq matn)
    assert is_session_free_text("🔐 Kirish (login)")
    assert is_session_free_text("📊 Sessiya holati")
    assert is_session_free_text("🚪 Chiqish (logout)")
    # Yopiq buyruqlar
    assert not is_session_free_text("")
    assert not is_session_free_text(None)
    assert not is_session_free_text("/loginn")          # prefiks mos kelmaydi
    assert not is_session_free_text("/xyz /login")      # faqat birinchi token tekshiriladi
    assert not is_session_free_text("📦 Ombor holati")
    assert not is_session_free_text("🏭 Ishlab chiqarish")


def test_claim_employee_telegram(db_session):
    """Birinchi kirish bootstrap: bo'sh telegram maydoni bog'lanadi,
    band maydon boshqa hisobga o'tkazilmaydi (deadlock tuzatildi)"""
    from database import models
    from utils import bot_auth

    emp = models.Employee(
        full_name="Claim Test", phone_number="+998907776655",
        position="Ishchi", department="Test",
        hire_date=datetime.utcnow(), salary=0, role="ishchi",
    )
    db_session.add(emp)
    db_session.commit()

    # Bo'sh maydon -> bog'lanadi
    assert bot_auth.claim_employee_telegram(db_session, emp, 313001) is True
    assert emp.telegram_id == 313001
    # Xuddi shu hisob -> True
    assert bot_auth.claim_employee_telegram(db_session, emp, 313001) is True
    # Boshqa hisob -> False (o'zgartirilmaydi)
    assert bot_auth.claim_employee_telegram(db_session, emp, 313002) is False
    assert emp.telegram_id == 313001
    # None xodim -> False
    assert bot_auth.claim_employee_telegram(db_session, None, 313003) is False
