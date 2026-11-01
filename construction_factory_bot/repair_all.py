#!/usr/bin/env python3
"""
Tizim xatoliklarini tuzatuvchi yagona skript:
1) database/crud.py dagi buzilgan create_sale_record ni tiklaydi
2) fix_all_v2.py dagi patch_oversell funksiyasini xavfsiz (idempotent) qiladi
3) Sintaksisni tekshiradi
"""
from pathlib import Path
import shutil
import sys
from datetime import datetime
import py_compile

ROOT = Path(__file__).parent.resolve()
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


# ============================================================
# 1) database/crud.py — buzilgan create_sale_record ni tuzatish
# ============================================================
def fix_crud():
    CRUD = ROOT / "database" / "crud.py"
    if not CRUD.exists():
        sys.exit(f"❌ Fayl topilmadi: {CRUD}")

    txt = CRUD.read_text(encoding="utf-8")

    START = "def create_sale_record(db: Session, *, product_id: int, quantity: float,"
    END = "    final_total = total_amount - (discount_amount or 0)"

    start = txt.find(START)
    if start == -1:
        sys.exit("❌ XATO: create_sale_record topilmadi")

    end = txt.find(END, start)
    if end == -1:
        sys.exit("❌ XATO: 'final_total = ...' qatori topilmadi")

    CORRECT = '''def create_sale_record(db: Session, *, product_id: int, quantity: float,
                       unit_price: float, total_amount: float,
                       discount_amount: float = 0.0,
                       advance_amount: Optional[float] = None,
                       payment_method: str = "cash",
                       payments: Optional[List[Dict]] = None,
                       customer: Optional[models.Customer] = None,
                       customer_name: str = None, customer_phone: str = None,
                       invoice_number: str = None,
                       user_id: int = 0, user_name: str = None) -> models.Sale:
    """
    Sotuvni jadvalga yozish (confirm_sale handler bilan bir xil hisob-kitob).

    XAVFSIZLIK (v4.x): OVERSELL HIMOYASI
    ------------------------------------
    Ikki parallel sotuvchi bir vaqtning o'zida bir xil mahsulotni so'rashi
    mumkin. Avval "available" ni o'qib, keyin yozish RACE CONDITION beradi.
    Yechim: SQLite'da write-lock (BEGIN IMMEDIATE) bilan atomik tekshirish,
    so'ngra barcha yozuvlarni BITTA commit'da amalga oshirish.

    Mavjud tranzaksiya mavjud bo'lsa (chaqiruvchi ochgan), yangi tranzaksiya
    ochmaymiz - DB API bu holatda xatolik bermaydi.

    - Chegirma qo'llanadi: final_total = total_amount - discount_amount
    - Nasiya (payment_method="credit"): advance qismi darhol to'lanadi,
      qolgan qism mijoz qarziga yoziladi (30 kun muddat)
    - Aralash to'lov (payments=[{"method": ..., "amount": ...}, ...]):
      bitta chekda naqd + karta + nasiya/payme/click/otkazma birga.
      Har bir usul uchun alohida Payment yozuvi, yig'indisi final_total ga
      teng bo'lishi shart. "credit" qismi qarzga yoziladi (is_credit=True).
      Sale.payment_method = "mixed" deb saqlanadi.
    - Sodiqlik ballari faqat haqiqatda olingan pulga beriladi
      (to'liq naqd/karta to'lov ham, nasiya avansi ham)
    - To'lov yozuvi, ombor harakati va audit log yaratiladi
    """
    from sqlalchemy import text as _sa_text

    is_sqlite = False
    try:
        is_sqlite = db.bind.dialect.name == "sqlite"
    except Exception:
        is_sqlite = False

    # SQLite'da write-lock olish (parallel o'qish uchun, boshqa yozuvchi kutadi)
    lock_acquired = False
    if is_sqlite and not db.in_transaction():
        try:
            db.execute(_sa_text("BEGIN IMMEDIATE"))
            lock_acquired = True
        except Exception:
            # Tranzaksiya allaqachon faol bo'lsa - jim o'tamiz
            lock_acquired = False

    try:
        available = get_available_product_qty(db, product_id)
        if available < quantity:
            raise ValueError(
                f"Omborda yetarli emas! Mavjud: {available:,.0f}, "
                f"so'ralgan: {quantity:,.0f}. Iltimos, qoldiqni tekshiring."
            )
    except ValueError:
        if lock_acquired:
            try:
                db.rollback()
            except Exception:
                pass
        raise
    except Exception as _e:
        # get_available_product_qty xatosi bo'lsa ham davom etamiz (backward-compat)
        pass
'''

    backup = CRUD.with_name(f"crud.py.broken_{STAMP}.bak")
    shutil.copy2(CRUD, backup)
    print(f"📦 Buzilgan crud.py zaxirasi: {backup.name}")

    new_txt = txt[:start] + CORRECT + "\n" + txt[end:]
    CRUD.write_text(new_txt, encoding="utf-8")
    print(f"✅ Tuzatildi: database/crud.py")


# ============================================================
# 2) fix_all_v2.py — patch_oversell ni idempotent qilish
# ============================================================
def fix_fixall_v2():
    FIX2 = ROOT / "fix_all_v2.py"
    if not FIX2.exists():
        print("⏭  fix_all_v2.py topilmadi — o'tkazib yuborildi")
        return

    txt = FIX2.read_text(encoding="utf-8")

    # patch_oversell funksiyasining boshini topish
    MARKER = 'def patch_oversell():\n    """create_sale_record boshida zaxira tekshiruvi + SQLite write-lock."""\n    p = ROOT / "database" / "crud.py"\n'

    if MARKER not in txt:
        print("⏭  patch_oversell bosh qismi topilmadi — qo'lda tuzatish kerak")
        return

    # Idempotentlik guard qo'shish
    GUARD = (
        'def patch_oversell():\n'
        '    """create_sale_record boshida zaxira tekshiruvi + SQLite write-lock."""\n'
        '    p = ROOT / "database" / "crud.py"\n'
        '\n'
        '    # IDEMPOTENTLIK: agar allaqachon qo\'llanilgan bo\'lsa, o\'tkazib yuborish\n'
        '    if p.exists() and "XAVFSIZLIK (v4.x): OVERSELL HIMOYASI" in p.read_text(encoding="utf-8"):\n'
        '        print("   ⏭  [crud: oversell lock] Allaqachon qo\'llanilgan — o\'tkazib yuborildi")\n'
        '        return\n'
    )

    backup = FIX2.with_name(f"fix_all_v2.py.bak_{STAMP}")
    shutil.copy2(FIX2, backup)
    print(f"📦 fix_all_v2.py zaxirasi: {backup.name}")

    txt = txt.replace(MARKER, GUARD, 1)
    FIX2.write_text(txt, encoding="utf-8")
    print(f"✅ Tuzatildi: fix_all_v2.py (idempotent guard qo'shildi)")


# ============================================================
# 3) Sintaksisni tekshirish
# ============================================================
def check_syntax():
    print("\n" + "=" * 60)
    print("🧪 SINTAKSIS TEKSHIRUVI")
    print("=" * 60)
    files = [
        "database/crud.py",
        "utils/event_store.py",
        "utils/notifications.py",
        "config.py",
        "fix_all_v2.py",
    ]
    all_ok = True
    for f in files:
        path = ROOT / f
        if not path.exists():
            print(f"   ⏭  {f} — topilmadi")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            print(f"   ✅ {f}")
        except py_compile.PyCompileError as e:
            print(f"   ❌ {f} — {e}")
            all_ok = False
    return all_ok


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🔧 TIZIMNI TUZATISH")
    print("=" * 60)

    print("\n[1/3] database/crud.py tuzatilmoqda...")
    fix_crud()

    print("\n[2/3] fix_all_v2.py xavfsizlantirilmoqda...")
    fix_fixall_v2()

    print("\n[3/3] Sintaksis tekshirilmoqda...")
    ok = check_syntax()

    print("\n" + "=" * 60)
    if ok:
        print("✅ BARCHASI TUZATILDI!")
        print("=" * 60)
        print("\nEndi testlarni ishga tushiring:")
        print("   python -m pytest tests/ -q --no-header 2>&1 | tail -50")
    else:
        print("⚠️  Ba'zi fayllarda xatolik qoldi — yuqoridagi xatolarni ko'ring")
        sys.exit(1)
