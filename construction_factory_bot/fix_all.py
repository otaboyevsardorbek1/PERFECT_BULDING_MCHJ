#!/usr/bin/env python3
"""
Construction Factory Bot — kritik xatolarni avtomatik tuzatish.
Ishlatish:  python fix_all.py
Rollback:   python fix_all.py --rollback .fix_backup_TIMESTAMP/
"""
import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f".fix_backup_{STAMP}"


# ============================================================
# YORDAMCHILAR
# ============================================================

def check_project():
    """Loyiha ildizida ekanligimizni tekshirish"""
    required = ["config.py", "main.py", "utils", "dashboard"]
    missing = [r for r in required if not (ROOT / r).exists()]
    if missing:
        sys.exit(f"❌ Loyiha ildizida emasmiz. Yetishmayapti: {missing}")


def backup_file(path: Path) -> bool:
    """Fayl zaxirasini oladi"""
    if not path.exists():
        return False
    rel = path.relative_to(ROOT)
    bp = BACKUP / rel
    bp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, bp)
    return True


def patch(path: Path, old: str, new: str, label: str) -> bool:
    """Fayldagi aniq matnni almashtiradi. Topilmasa — o'tkazib yuboradi."""
    if not path.exists():
        print(f"   ⚠️  [{label}] Fayl topilmadi: {path.relative_to(ROOT)}")
        return False
    txt = path.read_text(encoding="utf-8")
    if old not in txt:
        print(f"   ⚠️  [{label}] Matn topilmadi — o'tkazib yuborildi")
        return False
    if txt.count(old) > 1:
        print(f"   ⚠️  [{label}] Matn {txt.count(old)} marta topildi, birinchisi almashtirildi")
    backup_file(path)
    path.write_text(txt.replace(old, new, 1), encoding="utf-8")
    print(f"   ✅ [{label}]")
    return True


def patch_regex(path: Path, pattern: str, repl: str, label: str) -> bool:
    """Regex orqali patcha qiladi"""
    if not path.exists():
        return False
    txt = path.read_text(encoding="utf-8")
    new_txt, n = re.subn(pattern, repl, txt, count=1)
    if n == 0:
        print(f"   ⚠️  [{label}] Regex mos kelmadi — o'tkazib yuborildi")
        return False
    backup_file(path)
    path.write_text(new_txt, encoding="utf-8")
    print(f"   ✅ [{label}]")
    return True


def run(cmd, check=True):
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, check=False)


# ============================================================
# PATCHES
# ============================================================

def fix_config_import():
    """1) config.py — import paytida raise qilmaslik"""
    p = ROOT / "config.py"
    patch(p,
        'BOT_TOKEN = os.getenv("BOT_TOKEN")\n'
        'if not BOT_TOKEN:\n'
        '    raise ValueError("BOT_TOKEN .env faylida belgilanishi shart!")',
        'BOT_TOKEN = os.getenv("BOT_TOKEN", "")\n'
        '# Eslatma: import paytida raise qilmaymiz — testlar, CLI va\n'
        '# migratsiyalar ham bu modulni import qiladi. Bot ishga tushganda\n'
        '# BOT_TOKEN yo\'q bo\'lsa, Bot() konstruktori xato beradi.',
        "config: BOT_TOKEN import-time raise olib tashlandi")

    # ALLOW_UNLINKED_ADMIN_BYPASS flagini qo'shish (ADMIN_IDS satridan keyin)
    patch(p,
        'MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", ADMIN_IDS[0] if ADMIN_IDS else 0))',
        'MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID", ADMIN_IDS[0] if ADMIN_IDS else 0))\n'
        '\n'
        '# v4.x XAVFSIZLIK: ADMIN_IDS bypass FAQAT quyidagi flag true bo\'lsa ishlaydi.\n'
        '# Production\'da false qoldiring — admin ham /login qilishi shart.\n'
        '# Bootstrap uchun bir marta true qilib, admin sessiyasini oching.\n'
        'ALLOW_UNLINKED_ADMIN_BYPASS = os.getenv(\n'
        '    "ALLOW_UNLINKED_ADMIN_BYPASS", "false"\n'
        ').lower() == "true"',
        "config: ALLOW_UNLINKED_ADMIN_BYPASS flagi qo'shildi")

    # validate_config ni kuchaytirish
    patch(p,
        'def validate_config():\n'
        '    """Konfiguratsiyani tekshirish"""\n'
        '    \n'
        '    errors = []\n'
        '    \n'
        '    if not BOT_TOKEN:\n'
        '        errors.append("BOT_TOKEN belgilanishi shart!")',
        'def validate_config():\n'
        '    """Konfiguratsiyani tekshirish (bot ishga tushganda chaqiriladi)"""\n'
        '    \n'
        '    errors = []\n'
        '    \n'
        '    if not BOT_TOKEN:\n'
        '        errors.append("BOT_TOKEN belgilanishi shart! (.env faylini tekshiring)")',
        "config: validate_config yaxshilandi")


def fix_admin_bypass():
    """2) utils/bot_auth.py — admin bypass ni flag bilan himoyalash"""
    p = ROOT / "utils" / "bot_auth.py"
    patch(p,
        '''    # Eski tizim uzluksizligi: ADMIN_IDS'dagi superuser xodim yozuviga bog'lanmagan
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
            return None''',
        '''    # v4.x XAVFSIZLIK: ADMIN_IDS bypass faqat ALLOW_UNLINKED_ADMIN_BYPASS=true
    # bo'lganda ishlaydi (bootstrap uchun). Production'da admin ham /login qiladi.
    from config import ALLOW_UNLINKED_ADMIN_BYPASS
    if telegram_id in ADMIN_IDS and ALLOW_UNLINKED_ADMIN_BYPASS:
        from database import models
        linked = (
            db.query(models.Employee.id)
            .filter(models.Employee.telegram_id == telegram_id)
            .first()
        )
        if linked is None:
            logger.warning(
                "Admin bypass ishlatildi (ALLOW_UNLINKED_ADMIN_BYPASS=true): "
                "telegram_id=%s, xodim yozuvi yo'q", telegram_id,
            )
            return None''',
        "bot_auth: admin bypass flag bilan himoyalandi")


def fix_web_secret():
    """3) dashboard/auth.py — chmod fail bo'lsa aniq xato"""
    p = ROOT / "dashboard" / "auth.py"
    patch(p,
        '''    secret = secrets.token_hex(32)
    try:
        _SECRET_FILE.write_text(secret, encoding="utf-8")
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return secret''',
        '''    secret = secrets.token_hex(32)
    try:
        _SECRET_FILE.write_text(secret, encoding="utf-8")
        os.chmod(_SECRET_FILE, 0o600)
    except OSError as e:
        raise RuntimeError(
            f"XAVFSIZLIK: token imzolash kalitini saqlab bo'lmadi. "
            f"API_SECRET_KEY ni .env ga qo'shing yoki "
            f"{_SECRET_FILE.parent} papkaga yozish huquqi bering. Xato: {e}"
        ) from e
    return secret''',
        "dashboard/auth: .web_secret chmod fail-closed")


def fix_cost_middleware():
    """4) dashboard/app.py — CostVisibilityMiddleware fail-closed"""
    p = ROOT / "dashboard" / "app.py"
    # strip_cost_fields ni import qilish (agar yo'q bo'lsa)
    patch(p,
        '''from dashboard.auth import (
    AuthUser, TOKEN_TTL_SECONDS, WEB_TOKEN_COOKIE, create_web_session,
    decode_token, employee_2fa_enabled, find_employee_by_phone, get_web_user,
    issue_2fa_pending_token, require_role, revoke_session, strip_cost_fields,
    verify_2fa_code, verify_password,
)''',
        '''from dashboard.auth import (
    AuthUser, TOKEN_TTL_SECONDS, WEB_TOKEN_COOKIE, create_web_session,
    decode_token, employee_2fa_enabled, find_employee_by_phone, get_web_user,
    issue_2fa_pending_token, require_role, revoke_session, strip_cost_fields,
    verify_2fa_code, verify_password,
)

# Anonim foydalanuvchi uchun tannarx maydonlarini filtrlovchi yordamchi
_COST_FIELDS_ANON = frozenset({
    "price_per_unit", "production_cost", "profit_margin",
    "total_cost", "warehouse_value", "value",
})

def _strip_cost_fields_anon(data):
    """Rekursiv ravishda tannarx/narx maydonlarini olib tashlaydi"""
    if isinstance(data, dict):
        return {k: _strip_cost_fields_anon(v) for k, v in data.items()
                if k not in _COST_FIELDS_ANON}
    if isinstance(data, list):
        return [_strip_cost_fields_anon(item) for item in data]
    return data''',
        "dashboard/app: _strip_cost_fields_anon qo'shildi")

    # Middleware mantiqini almashtirish — fail-closed
    patch(p,
        '''        # Foydalanuvchi kirganmi? (get_current_user request.state.auth_user'ni to'ldiradi)
        user = getattr(request.state, "auth_user", None)
        if user is None or getattr(user, "see_cost", True):
            return response''',
        '''        # Foydalanuvchi kirganmi? (get_current_user request.state.auth_user'ni to'ldiradi)
        # XAVFSIZLIK (fail-closed): user aniqlanmasa yoki see_cost=False bo'lsa
        # javobdan tannarx maydonlarini filtrlab tashlaymiz. Auth javobgarligi
        # endpoint'da (401/403 o'zi qaytaradi).
        user = getattr(request.state, "auth_user", None)
        if user is not None and getattr(user, "see_cost", True):
            return response''',
        "dashboard/app: middleware fail-closed (1/2)")

    # Filtrlash qismi — user None bo'lsa ham ishlaydigan qilish
    patch(p,
        '''        # Javob tanasini o'qib, tannarx maydonlarini olib tashlash
        body = b"".join([chunk async for chunk in response.body_iterator])
        if not body:
            return response
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return response

        cleaned = strip_cost_fields(payload, user)
        new_body = json.dumps(cleaned, ensure_ascii=False).encode("utf-8")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(content=new_body, status_code=response.status_code,
                        headers=headers, media_type="application/json")''',
        '''        # Javob tanasini o'qib, tannarx maydonlarini olib tashlash
        body = b"".join([chunk async for chunk in response.body_iterator])
        if not body:
            return response
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return response

        # user=None bo'lsa (anonim) — qattiq filtr; aks holda rol bo'yicha
        if user is None:
            cleaned = _strip_cost_fields_anon(payload)
        else:
            cleaned = strip_cost_fields(payload, user)
        new_body = json.dumps(cleaned, ensure_ascii=False).encode("utf-8")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(content=new_body, status_code=response.status_code,
                        headers=headers, media_type="application/json")''',
        "dashboard/app: middleware fail-closed (2/2)")


def fix_confirm_payment():
    """5) dashboard/payments.py — _confirm_payment atomik"""
    p = ROOT / "dashboard" / "payments.py"
    patch(p,
        '''def _confirm_payment(db: Session, invoice: models.PaymentInvoice, *, gateway: str):
    """To'lov tasdiqlanganda: Payment yozuvi + mijoz qarzini yopish
    yoki web-do'kon buyurtmasini yakunlash (shop_order_id bo'lsa)."""
    if invoice.status == "paid":
        return  # ikki marta tasdiqlashni oldini olish (idempotent)
    invoice.status = "paid"
    invoice.paid_at = datetime.utcnow()
    db.commit()

    method = "payme" if gateway == "payme" else "click"''',
        '''def _confirm_payment(db: Session, invoice: models.PaymentInvoice, *, gateway: str):
    """To'lov tasdiqlanganda: Payment yozuvi + mijoz qarzini yopish
    yoki web-do'kon buyurtmasini yakunlash (shop_order_id bo'lsa).

    XAVFSIZLIK: bir nechta worker/webhook parallel kelishi mumkin.
    Shuning uchun status'ni ATOMIK shartli UPDATE orqali o'zgartiramiz —
    faqat BITTA chaqiruv "1" qaytaradi, qolganlari "0" va darhol qaytadi.
    """
    # 1. ATOMIK holat o'zgartirish: WHERE id=? AND status != 'paid'
    now = datetime.utcnow()
    updated = db.query(models.PaymentInvoice).filter(
        models.PaymentInvoice.id == invoice.id,
        models.PaymentInvoice.status != "paid",
    ).update(
        {"status": "paid", "paid_at": now},
        synchronize_session=False,
    )
    db.commit()
    if not updated:
        # Boshqa worker allaqachon tasdiqlagan — idempotent qaytamiz
        db.refresh(invoice)
        return
    db.refresh(invoice)

    method = "payme" if gateway == "payme" else "click"''',
        "payments: _confirm_payment atomik (race fix)")


def fix_verify_integrity():
    """6) utils/event_store.py — verify_event_integrity from_seq bilan"""
    p = ROOT / "utils" / "event_store.py"
    patch(p,
        '''    q = db.query(Event).filter(Event.sequence >= from_seq)
    if to_seq:
        q = q.filter(Event.sequence <= to_seq)
    
    events = q.order_by(Event.sequence.asc()).all()
    
    broken = []
    prev_checksum = None
    
    for event in events:''',
        '''    q = db.query(Event).filter(Event.sequence >= from_seq)
    if to_seq:
        q = q.filter(Event.sequence <= to_seq)
    
    events = q.order_by(Event.sequence.asc()).all()
    
    broken = []
    # XAVFSIZLIK: from_seq > 0 bo'lsa, avvalgi event'ning checksumi kerak,
    # aks holda BARCHA event'lar "buzilgan" deb noto'g'ri ko'rsatiladi.
    prev_checksum = None
    if from_seq > 0:
        prev_event = (db.query(Event)
                      .filter(Event.sequence < from_seq)
                      .order_by(Event.sequence.desc())
                      .first())
        if prev_event:
            prev_checksum = prev_event.checksum
    
    for event in events:''',
        "event_store: verify_event_integrity from_seq fix")


def fix_notifications():
    """7) utils/notifications.py — ADMIN_IDS check + immediate first check"""
    p = ROOT / "utils" / "notifications.py"

    # ADMIN_IDS bo'sh bo'lsa erta chiqish
    patch(p,
        '''    total = len(employees)
    success = 0
    failed = 0
    
    await bot_instance.send_message(
        chat_id=ADMIN_IDS[0] if ADMIN_IDS else 0,
        text=f"📢 *Ommaviy bildirishnoma boshlanmoqda...*\\n\\n"
             f"*Sarlavha:* {title}\\n"
             f"*Qabul qiluvchilar:* {total} ta",
        parse_mode=ParseMode.MARKDOWN
    )''',
        '''    total = len(employees)
    success = 0
    failed = 0
    
    if not ADMIN_IDS:
        logger.error("ADMIN_IDS bo'sh — progress xabari yuborilmadi")
        # Baribir xodimlarga yuborishni davom ettiramiz (progress ko'rsatmasdan)
        progress_chat_id = None
    else:
        progress_chat_id = ADMIN_IDS[0]
    
    if progress_chat_id is not None:
        await bot_instance.send_message(
            chat_id=progress_chat_id,
            text=f"📢 *Ommaviy bildirishnoma boshlanmoqda...*\\n\\n"
                 f"*Sarlavha:* {title}\\n"
                 f"*Qabul qiluvchilar:* {total} ta",
            parse_mode=ParseMode.MARKDOWN
        )''',
        "notifications: ADMIN_IDS bo'sh bo'lsa himoya")

    # Progress xabarida ham ADMIN_IDS[0] xavfsiz qilish
    patch(p,
        '''            # Har 10 ta yuborilganda progressni ko'rsatish
            if success % 10 == 0:
                progress = (success / total) * 100
                await bot_instance.send_message(
                    chat_id=ADMIN_IDS[0] if ADMIN_IDS else 0,
                    text=f"📊 *Progress:* {success}/{total} ({progress:.1f}%)",
                    parse_mode=ParseMode.MARKDOWN
                )''',
        '''            # Har 10 ta yuborilganda progressni ko'rsatish
            if success % 10 == 0 and progress_chat_id is not None:
                progress = (success / total) * 100
                await bot_instance.send_message(
                    chat_id=progress_chat_id,
                    text=f"📊 *Progress:* {success}/{total} ({progress:.1f}%)",
                    parse_mode=ParseMode.MARKDOWN
                )''',
        "notifications: progress chat_id xavfsiz")

    # notification_background_task — birinchi tekshiruv darhol
    patch(p,
        '''    manager = NotificationManager()
    
    while True:
        try:
            # Har 5 daqiqada avtomatik tekshiruv
            await asyncio.sleep(300)
            
            # Barcha bildirishnomalarni tekshirish
            await manager.check_all_notifications()''',
        '''    manager = NotificationManager()
    
    # Birinchi tekshiruvni DARHOL bajaramiz (5 daqiqa kutmаymiz)
    try:
        await manager.check_all_notifications()
    except Exception as _e:
        logger.warning(f"Boshlang'ich bildirishnoma tekshiruvida xatolik: {_e}")
    
    while True:
        try:
            # Har 5 daqiqada avtomatik tekshiruv
            await asyncio.sleep(300)
            
            # Barcha bildirishnomalarni tekshirish
            await manager.check_all_notifications()''',
        "notifications: birinchi tekshiruv darhol")


def fix_event_sourcing_test():
    """8) tests/test_api/test_event_sourcing.py — in-memory DB"""
    p = ROOT / "tests" / "test_api" / "test_event_sourcing.py"
    patch(p,
        '''@pytest.fixture
def db_session():
    """Test DB session"""
    from database.models import Base, engine
    from sqlalchemy.orm import sessionmaker
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSession()
    yield db
    db.close()''',
        '''@pytest.fixture
def db_session(tmp_path):
    """Test DB session — VAQTINCHALIK fayl, production DB'ga TEGMAYDI"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import models
    engine = create_engine(f"sqlite:///{tmp_path}/test_events.db")
    models.Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSession()
    yield db
    db.close()
    engine.dispose()''',
        "test_event_sourcing: in-memory DB (production DB himoya)")


# ============================================================
# MAIN
# ============================================================

PATCHES = [
    ("1. config.py — import-time raise olib tashlash", fix_config_import),
    ("2. utils/bot_auth.py — admin bypass flag bilan himoyalash", fix_admin_bypass),
    ("3. dashboard/auth.py — .web_secret chmod fail-closed", fix_web_secret),
    ("4. dashboard/app.py — CostVisibility fail-closed", fix_cost_middleware),
    ("5. dashboard/payments.py — _confirm_payment atomik", fix_confirm_payment),
    ("6. utils/event_store.py — verify_integrity from_seq", fix_verify_integrity),
    ("7. utils/notifications.py — ADMIN_IDS/backoff tuzatish", fix_notifications),
    ("8. tests/test_event_sourcing.py — in-memory DB", fix_event_sourcing_test),
]


def do_fix():
    check_project()
    print(f"\n📦 Zaxira nusxa papkasi: {BACKUP.name}\n")
    results = []
    for name, fn in PATCHES:
        print(f"\n🔧 {name}")
        try:
            fn()
            results.append((name, True))
        except Exception as e:
            print(f"   ❌ Xato: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("📊 NATIJALAR")
    print("=" * 60)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    print(f"\n💾 Zaxira: {BACKUP}")

    # Testlarni ishga tushirish
    print("\n" + "=" * 60)
    print("🧪 TESTLAR ISHGA TUSHIRILMOQDA")
    print("=" * 60)
    test = run(["python", "-m", "pytest", "tests/", "-q", "--no-header",
                "-x", "--timeout=120"], check=False)
    if test.returncode == 0:
        print("\n✅ Barcha testlar muvaffaqiyatli o'tdi!")
        print(f"\n🗑  Zaxirani o'chirish: rm -rf {BACKUP.name}")
    else:
        print(f"\n⚠️  Testlar muvaffaqiyatsiz ({test.returncode})")
        print(f"\n🔄 Rollback: python fix_all.py --rollback {BACKUP.name}")


def do_rollback(backup_dir: str):
    src = Path(backup_dir)
    if not src.exists() or not src.is_dir():
        sys.exit(f"❌ Backup papkasi topilmadi: {src}")
    print(f"🔄 Rollback: {src}")
    count = 0
    for item in src.rglob("*"):
        if item.is_file():
            rel = item.relative_to(src)
            target = ROOT / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            print(f"   ↩️  {rel}")
            count += 1
    print(f"\n✅ {count} ta fayl qaytarildi.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollback", metavar="BACKUP_DIR",
                    help="Zaxira nusxadan qaytarish")
    args = ap.parse_args()
    if args.rollback:
        do_rollback(args.rollback)
    else:
        do_fix()
