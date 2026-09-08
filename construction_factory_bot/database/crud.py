from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, extract
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
import uuid
from . import models

# =============== Xom ashyo CRUD ===============
def create_raw_material(db: Session, material_data: Dict) -> models.RawMaterial:
    """Yangi xom ashyo yaratish"""
    material = models.RawMaterial(**material_data)
    db.add(material)
    db.commit()
    db.refresh(material)
    return material

def get_raw_material(db: Session, material_id: int) -> Optional[models.RawMaterial]:
    """Xom ashyoni ID bo'yicha olish"""
    return db.query(models.RawMaterial).filter(models.RawMaterial.id == material_id).first()

def get_raw_materials(db: Session, skip: int = 0, limit: int = 100) -> List[models.RawMaterial]:
    """Barcha xom ashyolarni olish"""
    return db.query(models.RawMaterial).offset(skip).limit(limit).all()

def update_raw_material(db: Session, material_id: int, update_data: Dict) -> Optional[models.RawMaterial]:
    """Xom ashyoni yangilash"""
    material = get_raw_material(db, material_id)
    if material:
        for key, value in update_data.items():
            setattr(material, key, value)
        db.commit()
        db.refresh(material)
    return material

def delete_raw_material(db: Session, material_id: int) -> bool:
    """Xom ashyoni o'chirish"""
    material = get_raw_material(db, material_id)
    if material:
        db.delete(material)
        db.commit()
        return True
    return False

def check_low_stock_materials(db: Session) -> List[models.RawMaterial]:
    """Yetarli bo'lmagan xom ashyolarni topish"""
    return db.query(models.RawMaterial).filter(
        models.RawMaterial.current_stock <= models.RawMaterial.min_stock
    ).all()

# =============== Mahsulot CRUD ===============
def create_product(db: Session, product_data: Dict) -> models.Product:
    """Yangi mahsulot yaratish"""
    product = models.Product(**product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

def get_product(db: Session, product_id: int) -> Optional[models.Product]:
    """Mahsulotni ID bo'yicha olish"""
    return db.query(models.Product).filter(models.Product.id == product_id).first()

def get_products_by_category(db: Session, category: str) -> List[models.Product]:
    """Mahsulotlarni kategoriya bo'yicha olish"""
    return db.query(models.Product).filter(
        models.Product.category == category,
        models.Product.is_active == True
    ).all()


# =============== O'XSHASH MAHSULOT TAKLIFI (TZ: "Bu g'ishtga mos sement") ===============
def get_related_products(db: Session, product_id: int, limit: int = 5) -> List[models.Product]:
    """
    Tanlangan mahsulotga o'xshash mahsulotlarni tavsiya qilish (cross-sell).

    Qoida: bir xil kategoriyadagi, faol, omborda qoldig'i bor mahsulotlar.
    Kategoriya bo'yicha birorta ham topilmasa — narxi yaqin boshqa mahsulotlar.
    Bu TZ'dagi "o'xshash mahsulot taklifi" — mijoz g'isht olsa, mos sement/armatura
    taklif qilinadi va o'rtacha chek oshadi.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        return []

    # 1) Bir xil kategoriya + faol + qoldiq bor
    related = db.query(models.Product).filter(
        models.Product.category == product.category,
        models.Product.is_active == True,
        models.Product.id != product_id,
    ).order_by(models.Product.selling_price.desc()).limit(limit).all()

    # Qoldiqlarini filtrlash (omborda borlari)
    with_stock = []
    for p in related:
        try:
            qty = get_available_product_qty(db, p.id)
        except Exception:
            qty = 0
        if qty and qty > 0:
            with_stock.append(p)
    if with_stock:
        return with_stock[:limit]

    # 2) Kategoriyada yo'q bo'lsa — narxi yaqin boshqa mahsulotlar
    fallback = db.query(models.Product).filter(
        models.Product.is_active == True,
        models.Product.id != product_id,
    ).order_by(func.abs(models.Product.selling_price - (product.selling_price or 0))).limit(limit).all()
    return [p for p in fallback if get_available_product_qty(db, p.id) > 0][:limit]

# =============== Ishlab chiqarish buyurtmalari CRUD ===============
def create_production_order(db: Session, order_data: Dict) -> models.ProductionOrder:
    """Yangi ishlab chiqarish buyurtmasi yaratish"""
    # Order raqamini yaratish
    today = datetime.now()
    order_count = db.query(models.ProductionOrder).filter(
        extract('year', models.ProductionOrder.created_at) == today.year,
        extract('month', models.ProductionOrder.created_at) == today.month
    ).count() + 1
    
    order_number = f"PO-{today.strftime('%Y%m')}-{order_count:04d}"
    order_data['order_number'] = order_number
    
    order = models.ProductionOrder(**order_data)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

# =============== Xodimlar CRUD ===============
def create_employee(db: Session, employee_data: Dict) -> models.Employee:
    """Yangi xodim yaratish"""
    employee = models.Employee(**employee_data)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee

def get_employee_by_telegram_id(db: Session, telegram_id: int) -> Optional[models.Employee]:
    """Xodimni Telegram ID bo'yicha olish"""
    return db.query(models.Employee).filter(
        models.Employee.telegram_id == telegram_id
    ).first()

def get_employees_by_department(db: Session, department: str) -> List[models.Employee]:
    """Xodimlarni bo'lim bo'yicha olish"""
    return db.query(models.Employee).filter(
        models.Employee.department == department,
        models.Employee.status == models.EmployeeStatus.ACTIVE
    ).all()

# =============== Ish vaqtlari CRUD ===============
def add_work_hours(db: Session, work_data: Dict) -> models.WorkHours:
    """Ish vaqtini kiritish"""
    work_hours = models.WorkHours(**work_data)
    db.add(work_hours)
    db.commit()
    db.refresh(work_hours)
    return work_hours

def get_employee_work_hours(db: Session, employee_id: int, start_date: date, end_date: date) -> List[models.WorkHours]:
    """Xodimning ish vaqtlarini olish"""
    return db.query(models.WorkHours).filter(
        models.WorkHours.employee_id == employee_id,
        models.WorkHours.date >= start_date,
        models.WorkHours.date <= end_date
    ).order_by(models.WorkHours.date).all()

# =============== Maosh to'lovlari CRUD ===============
def create_salary_payment(db: Session, salary_data: Dict) -> models.SalaryPayment:
    """Maosh to'lovini yaratish"""
    payment = models.SalaryPayment(**salary_data)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment

def get_employee_salary_payments(db: Session, employee_id: int, year: int = None, month: int = None) -> List[models.SalaryPayment]: # type: ignore
    """Xodimning maosh to'lovlarini olish"""
    query = db.query(models.SalaryPayment).filter(
        models.SalaryPayment.employee_id == employee_id
    )
    
    if year:
        query = query.filter(models.SalaryPayment.year == year)
    if month:
        query = query.filter(models.SalaryPayment.month == month)
    
    return query.order_by(desc(models.SalaryPayment.year), desc(models.SalaryPayment.month)).all()

# =============== Statistika va hisobotlar ===============
def get_warehouse_statistics(db: Session) -> Dict:
    """Ombor statistikasini hisoblash"""
    # Xom ashyo umumiy qiymati
    raw_materials_value = db.query(
        func.sum(models.RawMaterial.current_stock * models.RawMaterial.price_per_unit)
    ).scalar() or 0
    
    # Mahsulotlar umumiy qiymati
    products_value = db.query(
        func.sum(models.Product.selling_price)
    ).filter(models.Product.is_active == True).scalar() or 0
    
    # Yetarli bo'lmagan materiallar
    low_stock_count = db.query(models.RawMaterial).filter(
        models.RawMaterial.current_stock <= models.RawMaterial.min_stock
    ).count()
    
    return {
        "total_raw_materials_value": raw_materials_value,
        "total_products_value": products_value,
        "low_stock_materials_count": low_stock_count,
        "total_materials_count": db.query(models.RawMaterial).count(),
        "total_products_count": db.query(models.Product).filter(models.Product.is_active == True).count()
    }

def get_production_statistics(db: Session, start_date: date, end_date: date) -> Dict:
    """Ishlab chiqarish statistikasini hisoblash"""
    # Ishlab chiqarish buyurtmalari statistikasi
    orders = db.query(models.ProductionOrder).filter(
        models.ProductionOrder.created_at >= start_date,
        models.ProductionOrder.created_at <= end_date
    ).all()
    
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o.status == models.OrderStatus.COMPLETED]) # type: ignore
    total_quantity = sum([o.quantity for o in orders])
    total_cost = sum([o.total_cost or 0 for o in orders])
    total_revenue = sum([o.total_revenue or 0 for o in orders])
    total_profit = total_revenue - total_cost
    
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "completion_rate": (completed_orders / total_orders * 100) if total_orders > 0 else 0,
        "total_quantity": total_quantity,
        "total_cost": total_cost,
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "avg_profit_per_order": total_profit / total_orders if total_orders > 0 else 0
    }

def get_financial_statistics(db: Session, start_date: date, end_date: date) -> Dict:
    """Moliya statistikasini hisoblash"""
    # Sotuvlar statistikasi
    sales = db.query(models.Sale).filter(
        models.Sale.sale_date >= start_date,
        models.Sale.sale_date <= end_date
    ).all()
    
    total_sales = len(sales)
    total_sales_amount = sum([s.total_amount for s in sales])
    
    # Xarajatlar statistikasi (ishlab chiqarish xarajatlari + maosh)
    production_costs = db.query(func.sum(models.ProductionOrder.total_cost)).filter(
        models.ProductionOrder.created_at >= start_date,
        models.ProductionOrder.created_at <= end_date
    ).scalar() or 0
    
    salary_costs = db.query(func.sum(models.SalaryPayment.total_amount)).filter(
        models.SalaryPayment.payment_date >= start_date,
        models.SalaryPayment.payment_date <= end_date,
        models.SalaryPayment.status == "paid"
    ).scalar() or 0
    
    total_costs = production_costs + salary_costs
    net_profit = total_sales_amount - total_costs
    
    return {
        "total_sales": total_sales,
        "total_sales_amount": total_sales_amount,
        "production_costs": production_costs,
        "salary_costs": salary_costs,
        "total_costs": total_costs,
        "net_profit": net_profit,
        "profit_margin": (net_profit / total_sales_amount * 100) if total_sales_amount > 0 else 0  # type: ignore
    }

# =============== Tizim loglari CRUD ===============
def create_system_log(db: Session, user_id: int = None, user_name: str = None,
                     action: str = "", module: str = "",
                     details: str = None, ip_address: str = None) -> models.SystemLog:
    """Tizim logini yaratish"""
    log = models.SystemLog(
        user_id=user_id,
        user_name=user_name,
        action=action,
        module=module,
        details=details,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# =============== Bildirishnomalar CRUD ===============
def create_notification(db: Session, notification_data: Dict) -> models.Notification:
    """Yangi bildirishnoma yaratish"""
    notification = models.Notification(**notification_data)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

def get_pending_notifications(db: Session) -> List[models.Notification]:
    """Kutilayotgan bildirishnomalarni olish"""
    return db.query(models.Notification).filter(
        models.Notification.status == models.NotificationStatus.PENDING,
        or_(
            models.Notification.scheduled_time.is_(None),
            models.Notification.scheduled_time <= datetime.utcnow()
        )
    ).order_by(models.Notification.priority.desc(), models.Notification.created_at).all()

def mark_notification_sent(db: Session, notification_id: int) -> bool:
    """Bildirishnomani yuborilgan deb belgilash"""
    notification = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if notification:
        notification.status = models.NotificationStatus.SENT # type: ignore
        notification.sent_time = datetime.utcnow() # type: ignore
        db.commit()
        return True
    return False


# ==================================================================
#  v3 MODULLAR: MIJOZ (CRM), NASIYA, YETKAZIB BERUVCHI, REZERVATSIYA,
#  KONVERTATSIYA, KO'CHIRISH, INVENTARIZATSIYA, MOLIYA
# ==================================================================

# =============== MIJOZLAR (CRM) ===============
def create_customer(db: Session, data: Dict) -> models.Customer:
    """Yangi mijoz yaratish"""
    customer = models.Customer(**data)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer

def get_customer(db: Session, customer_id: int) -> Optional[models.Customer]:
    """Mijozni ID bo'yicha olish"""
    return db.query(models.Customer).filter(models.Customer.id == customer_id).first()

def get_customer_by_phone(db: Session, phone: str) -> Optional[models.Customer]:
    """Mijozni telefon raqami bo'yicha qidirish"""
    return db.query(models.Customer).filter(models.Customer.phone == phone).first()

def search_customers(db: Session, query: str, limit: int = 20) -> List[models.Customer]:
    """Mijozlarni nomi/telefon/kompaniya bo'yicha qidirish"""
    q = f"%{query}%"
    return db.query(models.Customer).filter(
        or_(
            models.Customer.name.ilike(q),
            models.Customer.phone.ilike(q),
            models.Customer.company.ilike(q),
        )
    ).order_by(models.Customer.name).limit(limit).all()

def list_customers(db: Session, skip: int = 0, limit: int = 100) -> List[models.Customer]:
    """Barcha mijozlar ro'yxati"""
    return db.query(models.Customer).order_by(models.Customer.name).offset(skip).limit(limit).all()

def update_customer(db: Session, customer_id: int, data: Dict) -> Optional[models.Customer]:
    """Mijoz ma'lumotlarini yangilash"""
    customer = get_customer(db, customer_id)
    if customer:
        for k, v in data.items():
            setattr(customer, k, v)
        db.commit()
        db.refresh(customer)
    return customer


# =============== SOTUV YOZUVLARI (v3: nasiya / aralash to'lov) ===============
def calc_loyalty_points(purchase_amount: float) -> int:
    """Sodiqlik ballari: haqiqatda olingan har 100 000 so'mga 1 ball"""
    return int((purchase_amount or 0) / 100000)


def create_sale_record(db: Session, *, product_id: int, quantity: float,
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
    final_total = total_amount - (discount_amount or 0)

    if payments:
        # ===== Aralash to'lov =====
        paid_entries = [p for p in payments if p.get("method") != "credit"]
        credit_entries = [p for p in payments if p.get("method") == "credit"]
        for p in payments:
            if p.get("method") not in ("cash", "card", "payme", "click", "transfer", "credit"):
                raise ValueError(f"Noma'lum to'lov usuli: {p.get('method')}")
            if float(p.get("amount", 0)) <= 0:
                raise ValueError("To'lov miqdori 0 dan katta bo'lishi kerak")
        total_paid = round(sum(float(p.get("amount", 0)) for p in paid_entries), 2)
        credit_amount = round(sum(float(p.get("amount", 0)) for p in credit_entries), 2)
        if round(total_paid + credit_amount, 2) != round(final_total, 2):
            raise ValueError(
                f"To'lovlar yig'indisi ({total_paid + credit_amount:,.0f} so'm) "
                f"jami summaga ({final_total:,.0f} so'm) teng emas"
            )
        is_credit = credit_amount > 0
        advance = total_paid
        debt_amount = credit_amount
        sale_payment_method = "mixed"
    else:
        # ===== Yagona to'lov usuli =====
        is_credit = payment_method == "credit"
        advance = final_total if advance_amount is None else advance_amount
        if is_credit:
            advance = min(advance, final_total)
        else:
            advance = final_total
        debt_amount = final_total - advance if is_credit else 0.0
        sale_payment_method = payment_method

    if not invoice_number:
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    sale = models.Sale(
        invoice_number=invoice_number,
        product_id=product_id,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=final_total,
        discount_amount=discount_amount or 0,
        paid_amount=advance,
        customer_id=customer.id if customer else None,
        customer_name=customer_name,
        customer_phone=customer_phone,
        payment_method=sale_payment_method,
        is_credit=is_credit,
        credit_days=30 if is_credit else 0,
        due_date=(datetime.utcnow() + timedelta(days=30)) if is_credit else None,
        credit_status=("tolanmagan" if is_credit and debt_amount > 0 else "toliq_tolangan"),
        sale_type="wholesale" if (customer and customer.is_wholesale) else "retail",
        status="completed",
        sale_date=datetime.utcnow(),
        user_id=user_id or None,
        user_name=user_name,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)

    # To'lov yozuvlari (aralash to'lovda har bir usul uchun alohida qator)
    if payments:
        for p in paid_entries:
            register_sale_payment(
                db, sale, amount=p["amount"], method=p["method"],
                note=f"Sotuv #{sale.invoice_number} (aralash)",
                created_by=user_name,
            )
    elif advance > 0:
        register_sale_payment(
            db, sale, amount=advance,
            method=("cash" if is_credit else payment_method),
            note=f"Sotuv #{sale.invoice_number}",
            created_by=user_name,
        )

    # Mijoz hisobini yangilash (xaridlar, qarz, ballar)
    if customer:
        customer.total_purchases = (customer.total_purchases or 0) + final_total
        if is_credit:
            customer.total_debt = (customer.total_debt or 0) + debt_amount
        if advance > 0:
            add_loyalty_points(db, customer, advance)  # ichida commit qiladi
        else:
            db.commit()

    # Ombordagi harakat yozuvi
    db.add(models.WarehouseTransaction(
        product_id=product_id,
        quantity=quantity,
        transaction_type=models.TransactionType.SALE,
        user_id=user_id,
        user_name=user_name,
        notes=f"Sotuv #{sale.invoice_number}"
    ))
    db.commit()

    # Audit log
    try:
        create_system_log(
            db, user_id=user_id, user_name=user_name,
            action=f"Sotuv: {sale.invoice_number} {final_total:,.0f} so'm ({sale_payment_method})",
            module="sales"
        )
    except Exception:
        pass

    return sale


def check_credit_limit(db: Session, customer: models.Customer, amount: float) -> Dict:
    """
    Nasiya (kredit) sotuviga ruxsat bormi?
    - Mijoz bloklangan bo'lsa -> rad etiladi
    - Kredit limiti 0 bo'lsa -> nasiya umuman yoqilmagan
    - current debt + yangi summa limitdan oshsa -> rad etiladi
    """
    if customer.status == models.CustomerStatus.BLOCKED.value:
        return {"allowed": False, "reason": "Mijoz bloklangan (qarzi bor). Direktor bilan bog'laning."}

    if customer.credit_limit <= 0:
        return {"allowed": False, "reason": "Bu mijoz uchun nasiya yoqilmagan (kredit limiti 0)."}

    free_limit = customer.credit_limit - customer.total_debt
    if free_limit < amount:
        return {
            "allowed": False,
            "reason": (
                f"Kredit limiti yetmaydi! Limiti: {customer.credit_limit:,.0f} so'm, "
                f"joriy qarzi: {customer.total_debt:,.0f} so'm, "
                f"bo'sh limit: {max(free_limit, 0):,.0f} so'm."
            ),
        }
    return {"allowed": True, "free_limit": free_limit}


def register_sale_payment(db: Session, sale: models.Sale,
                          amount: float, method: str = "cash",
                          note: str = None, created_by: str = None) -> models.Payment:
    """Sotuvga to'lov yozish (aralash to'lovda bir necha marta chaqiriladi)"""
    payment = models.Payment(
        sale_id=sale.id,
        customer_id=sale.customer_id,
        amount=amount,
        method=method,
        payment_type="sale" if not sale.is_credit else "debt",
        note=note,
        created_by=created_by,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def pay_customer_debt(db: Session, customer_id: int, amount: float,
                      method: str = "cash", note: str = None,
                      created_by: str = None) -> Optional[Dict]:
    """Mijoz qarzini to'lash (eng eski nasiya sotuvlariga ketma-ket yopiladi - FIFO)"""
    customer = get_customer(db, customer_id)
    if not customer:
        return None

    remaining = amount
    # Qarzi bor nasiya sotuvlarini eng eski bo'yicha olish
    credit_sales = db.query(models.Sale).filter(
        models.Sale.customer_id == customer_id,
        models.Sale.is_credit == True,
        models.Sale.credit_status != models.CreditStatus.PAID.value,
    ).order_by(models.Sale.sale_date).all()

    for sale in credit_sales:
        if remaining <= 0:
            break
        sale_paid = sale.paid_amount or 0
        sale_total = sale.total_amount or 0
        sale_remaining = sale_total - sale_paid
        if sale_remaining <= 0:
            continue
        pay = min(remaining, sale_remaining)
        sale.paid_amount = sale_paid + pay
        sale.credit_status = (
            models.CreditStatus.PAID.value
            if sale.paid_amount >= sale_total
            else models.CreditStatus.PARTIAL.value
        )
        remaining -= pay
        db.add(models.Payment(
            sale_id=sale.id, customer_id=customer_id, amount=pay,
            method=method, payment_type="debt",
            note=note or f"Qarz to'lovi #{sale.invoice_number}",
            created_by=created_by,
        ))

    paid_actual = amount - remaining
    customer.total_debt = max(customer.total_debt - paid_actual, 0)
    # Qarz to'lovi ham haqiqiy pul tushumi — sodiqlik ballari beriladi
    points_earned = calc_loyalty_points(paid_actual)
    customer.loyalty_points = (customer.loyalty_points or 0) + points_earned
    db.commit()
    return {"paid": paid_actual, "new_debt": customer.total_debt,
            "points_earned": points_earned}


def add_loyalty_points(db: Session, customer: models.Customer, purchase_amount: float):
    """Sodiqlik bonusi qo'shish — haqiqatda olingan pulga ball"""
    points = calc_loyalty_points(purchase_amount)  # 100 ming so'm -> 1 ball
    customer.loyalty_points = (customer.loyalty_points or 0) + points
    db.commit()
    return points


# =============== MIJOZ TRIAJI (Oltin / Kumush / Bronza) ===============
# TZ: "Kim ko'p va tez to'laydi — Oltin mijoz; kim qarzini kechiktirsa —
#      avtomatik SMS eslatma; kim 3 oy xarid qilmasa — 'Qaytib kel' kupon."
# Quyidagi chegaralar .env orqali sozlanadi (so'm):
#   CUSTOMER_TIER_GOLD_THRESHOLD (default 50 000 000)
#   CUSTOMER_TIER_SILVER_THRESHOLD (default 10 000 000)
#   CUSTOMER_TIER_INACTIVE_DAYS (default 90)
TIER_LABELS = {"gold": "🏅 Oltin mijoz", "silver": "🥈 Kumush mijoz", "bronze": "🥉 Bronza mijoz"}


def get_customer_tier_thresholds() -> Dict[str, float]:
    """Triaj chegaralarini olish (.env dan sozlanishi mumkin)"""
    import os
    return {
        "gold": float(os.getenv("CUSTOMER_TIER_GOLD_THRESHOLD", "50000000")),
        "silver": float(os.getenv("CUSTOMER_TIER_SILVER_THRESHOLD", "10000000")),
        "inactive_days": int(os.getenv("CUSTOMER_TIER_INACTIVE_DAYS", "90")),
    }


def calculate_customer_tier(db: Session, customer: models.Customer) -> str:
    """
    Mijoz triajini aniqlash (dinamik hisob):
      - Oltin:   jami xarid >= gold_threshold VA joriy qarz xaridning 50% dan oshmagan
      - Kumush:  jami xarid >= silver_threshold (qarz cheklovi gold'ga nisbatan yumshoq)
      - Bronza:  qolganlar (shu jumladan VIP holat o'chirilganlar)
    Eslatma: muddati o'tgan qarz bo'lsa daraja bir pog'ona pastga tushadi.
    """
    thresholds = get_customer_tier_thresholds()
    purchases = customer.total_purchases or 0
    debt = customer.total_debt or 0

    tier = "bronze"
    if purchases >= thresholds["gold"]:
        tier = "gold"
    elif purchases >= thresholds["silver"]:
        tier = "silver"

    # Qarz nisbati oshib ketsa — darajani pasaytirish (Oltin->Kumush, Kumush->Bronza)
    if debt > purchases * 0.5 and tier in ("gold", "silver"):
        tier = "silver" if tier == "gold" else "bronze"

    # Muddati o'tgan qarz bor bo'lsa — bronza
    overdue = db.query(models.Sale).filter(
        models.Sale.customer_id == customer.id,
        models.Sale.is_credit == True,
        models.Sale.credit_status == "muddati_otgan",
    ).first()
    if overdue:
        tier = "bronze"

    return tier


def get_customer_tier_label(tier: str) -> str:
    """Triaj yorlig'ini olish"""
    return TIER_LABELS.get(tier, TIER_LABELS["bronze"])


def list_customers_by_tier(db: Session, tier: str, limit: int = 100) -> List[models.Customer]:
    """Ma'lum toifadagi mijozlar ro'yxati (Oltin/Kumush/Bronza)"""
    customers = list_customers(db, limit=limit)
    return [c for c in customers if calculate_customer_tier(db, c) == tier]


def get_customer_segmentation(db: Session) -> Dict:
    """CRM segmentatsiya statistikasi: har bir toifadagi mijozlar soni"""
    customers = db.query(models.Customer).all()
    seg = {"gold": 0, "silver": 0, "bronze": 0}
    for c in customers:
        seg[calculate_customer_tier(db, c)] += 1
    seg["total"] = len(customers)
    return seg


def customer_to_dict(db: Session, customer: models.Customer) -> Dict:
    """Mijozni dict ga o'tkazish (API uchun) — triaj bilan birga"""
    tier = calculate_customer_tier(db, customer)
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "company": customer.company,
        "address": customer.address,
        "credit_limit": customer.credit_limit or 0,
        "total_debt": customer.total_debt or 0,
        "total_purchases": customer.total_purchases or 0,
        "loyalty_points": customer.loyalty_points or 0,
        "is_wholesale": customer.is_wholesale,
        "status": customer.status,
        "tier": tier,
        "tier_label": get_customer_tier_label(tier),
        "notes": customer.notes,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
    }


# =============== QAYTARISH AKTI (RETURN) ===============
# TZ: Mijoz tovarni qaytarsa -> pul qaytarish / almashtirish / bonus ball.
# Qoida: sotuvdan keyin 7 kun ichida va mahsulot ishlatilmagan bo'lsa.
RETURN_REASON_LABELS = {
    "brak": "Sifat muammosi (brak)",
    "notogri": "Noto'g'ri mahsulot",
    "mijoz_istagi": "Mijoz istagi",
}
RETURN_TYPE_LABELS = {
    "cash": "Naqd pul qaytarish",
    "card": "Kartaga pul qaytarish",
    "bonus": "Bonus ball berish",
    "exchange": "Boshqa mahsulotga almashtirish",
}


def check_return_eligibility(db: Session, sale_id: int, quantity: float = None) -> Dict:
    """
    Qaytarishga ruxsat bormi?
    - Sotuv topilishi va hali to'liq qaytarilmagan bo'lishi kerak
    - Qaytariladigan miqdor qoldiqdan oshmasligi kerak
    - Sotuv RETURN_PERIOD_DAYS (standart 7 kun) ichida bo'lishi kerak
    """
    from config import RETURN_PERIOD_DAYS
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        return {"allowed": False, "reason": "Sotuv topilmadi.", "sale": None}
    remaining = (sale.quantity or 0) - (sale.returned_qty or 0)
    if sale.status == "qaytarilgan" or remaining <= 1e-9:
        return {"allowed": False, "reason": "Bu sotuv to'liq qaytarilgan — qaytariladigan miqdor qolmagan.", "sale": sale}
    if quantity is not None:
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            return {"allowed": False, "reason": "Qaytariladigan miqdor son bo'lishi kerak.", "sale": sale}
        if quantity <= 0:
            return {"allowed": False, "reason": "Qaytariladigan miqdor musbat son bo'lishi kerak.", "sale": sale}
        if quantity > remaining + 1e-9:
            return {"allowed": False, "reason": f"Qaytariladigan miqdor qoldiqdan oshadi (qoldiq: {remaining:,.0f}).", "sale": sale}
    sale_date = sale.sale_date or sale.created_at
    if sale_date:
        age = datetime.utcnow() - sale_date
        if age > timedelta(days=RETURN_PERIOD_DAYS):
            return {"allowed": False, "reason": f"Qaytarish muddati o'tgan (sotuvdan {RETURN_PERIOD_DAYS} kun o'tdi).", "sale": sale}
    return {"allowed": True, "remaining": remaining, "sale": sale}


def create_return_act(db: Session, *, sale_id: int, quantity: float,
                      reason: str = "mijoz_istagi",
                      refund_type: str = "cash",
                      exchange_product_id: int = None,
                      exchange_quantity: float = None,
                      refund_method: str = None,
                      note: str = None,
                      user_id: int = 0, user_name: str = None) -> models.ReturnAct:
    """
    Qaytarish aktini bajarish (TZ F bo'limi):
    1. Ruxsat tekshiruvi (7 kun + ishlatilmagan + qoldiq yetarli)
    2. Pul qaytarish / almashtirish / bonus ball tanlanadi
    3. Tovar omborga qaytadi (sifatsiz bo'lsa — brak ombori)
    4. Sotuv tarixiga "qaytarilgan" qayd etiladi, mijoz hisobi yangilanadi
    5. To'lov/ballar/ombor/log yozuvlari saqlanadi

    Moliyaviy mantiq:
    - Nasiya qismi avval mijoz qarzidan hisobdan chiqariladi
    - Qolgan (mijoz to'lagan) qism refund_type bo'yicha qaytariladi:
      cash/card -> pul (manfiy Payment yozuvi), bonus -> ball, exchange -> yangi mahsulot
    """
    check = check_return_eligibility(db, sale_id, quantity)
    if not check["allowed"]:
        raise ValueError(check["reason"])
    sale = check["sale"]
    quantity = float(quantity)

    product = db.query(models.Product).filter(models.Product.id == sale.product_id).first()
    if not product:
        raise ValueError("Mahsulot topilmadi.")

    reason = str(reason or "mijoz_istagi").lower()
    refund_type = str(refund_type or "cash").lower()
    if refund_type not in ("cash", "card", "bonus", "exchange"):
        raise ValueError("Noto'g'ri qaytarish turi.")
    method = refund_type if refund_type in ("cash", "card") else (refund_method or "cash")

    unit_price = sale.unit_price or 0
    x_value = round(quantity * unit_price, 2)  # qaytarilgan tovar qiymati
    receivable = max((sale.total_amount or 0) - (sale.paid_amount or 0) - (sale.returned_amount or 0), 0)
    debt_reduction = round(min(x_value, receivable), 2)  # qarzdan chiqariladigan qism
    cash_part = round(max(x_value - debt_reduction, 0), 2)  # mijoz to'lagan qism

    # Almashtirish (exchange) ma'lumotlari
    exchange_product = None
    exchange_value = 0.0
    tradein_amount = 0.0
    extra_amount = 0.0
    if refund_type == "exchange":
        if receivable > 1e-9:
            raise ValueError("Almashtirish faqat to'liq to'langan sotuvlar uchun (qarzi bor sotuvda avval qarzni yoping).")
        if not exchange_product_id:
            raise ValueError("Almashtirish uchun yangi mahsulot tanlanmagan.")
        exchange_product = db.query(models.Product).filter(
            models.Product.id == exchange_product_id,
            models.Product.is_active == True,
        ).first()
        if not exchange_product:
            raise ValueError("Almashtiriladigan mahsulot topilmadi.")
        try:
            exchange_quantity = float(exchange_quantity or 0)
        except (TypeError, ValueError):
            raise ValueError("Almashtiriladigan miqdor noto'g'ri.")
        if exchange_quantity <= 0:
            raise ValueError("Almashtiriladigan miqdor musbat son bo'lishi kerak.")
        exchange_value = round(exchange_quantity * (exchange_product.selling_price or 0), 2)
        tradein_amount = round(min(x_value, exchange_value), 2)
        if exchange_value > x_value:
            extra_amount = round(exchange_value - x_value, 2)  # mijoz qo'shimcha to'laydi
        else:
            cash_part = round(x_value - exchange_value, 2)  # ortiqcha qism qaytariladi

    # Pul / ball hisob-kitobi
    refund_amount = 0.0
    bonus_points = 0.0
    if refund_type in ("cash", "card"):
        refund_amount = cash_part
    elif refund_type == "bonus":
        bonus_points = float(calc_loyalty_points(cash_part))
    elif refund_type == "exchange" and exchange_value < x_value:
        refund_amount = round(x_value - exchange_value, 2)

    customer = db.query(models.Customer).filter(models.Customer.id == sale.customer_id).first() if sale.customer_id else None

    # Akt raqami: RTN-YYYYMM-NNNN
    now = datetime.now()
    act_count = db.query(models.ReturnAct).filter(
        extract("year", models.ReturnAct.created_at) == now.year,
        extract("month", models.ReturnAct.created_at) == now.month,
    ).count() + 1
    act_number = f"RTN-{now.strftime('%Y%m')}-{act_count:04d}"

    # Almashtirish: yangi mahsulot sotuvi (trade-in chegirma bilan)
    new_sale = None
    if refund_type == "exchange":
        new_sale = create_sale_record(
            db,
            product_id=exchange_product.id,
            quantity=exchange_quantity,
            unit_price=exchange_product.selling_price or 0,
            total_amount=exchange_value,
            discount_amount=tradein_amount,
            advance_amount=extra_amount,
            payment_method=method,
            customer=customer,
            customer_name=sale.customer_name,
            customer_phone=sale.customer_phone,
            user_id=user_id,
            user_name=user_name,
        )

    # Sotuv holatini yangilash ("Qaytarildi" tarixga yoziladi)
    sale.returned_qty = (sale.returned_qty or 0) + quantity
    sale.returned_amount = (sale.returned_amount or 0) + x_value
    if (sale.quantity or 0) - sale.returned_qty <= 1e-9:
        sale.status = "qaytarilgan"
    outstanding = (sale.total_amount or 0) - (sale.paid_amount or 0) - (sale.returned_amount or 0)
    if outstanding <= 1e-9:
        sale.credit_status = models.CreditStatus.PAID.value

    # Mijoz hisobini yangilash
    if customer:
        customer.total_purchases = max((customer.total_purchases or 0) - x_value, 0)
        customer.total_debt = max((customer.total_debt or 0) - debt_reduction, 0)
        if refund_amount > 0:
            # Qaytarilgan pul uchun ilgari berilgan ballarni qaytarib olamiz
            customer.loyalty_points = max((customer.loyalty_points or 0) - calc_loyalty_points(refund_amount), 0)
        elif bonus_points > 0:
            # Bonus turi: mijozga kelajakdagi xarid uchun ball yoziladi
            customer.loyalty_points = (customer.loyalty_points or 0) + bonus_points

    # Pul qaytarish yozuvi (manfiy to'lov — chiqim)
    if refund_amount > 0:
        db.add(models.Payment(
            sale_id=sale.id,
            customer_id=sale.customer_id,
            amount=-refund_amount,
            method=method,
            payment_type="refund",
            note=f"Qaytarish #{act_number}: {product.name} x {quantity} {product.unit}",
            created_by=user_name,
        ))

    # Tovar omborga qaytadi (sifatsiz bo'lsa — brak ombori)
    target_wh = "brak" if reason == "brak" else (product.warehouse or "tayyor")
    db.add(models.WarehouseTransaction(
        product_id=product.id,
        quantity=quantity,
        transaction_type=models.TransactionType.RETURN,
        user_id=user_id,
        user_name=user_name,
        document_number=act_number,
        counterparty=sale.customer_name or "Mijoz",
        target_warehouse=target_wh,
        notes=f"Qaytarish #{act_number}: {RETURN_REASON_LABELS.get(reason, reason)}",
    ))

    act = models.ReturnAct(
        act_number=act_number,
        sale_id=sale.id,
        customer_id=sale.customer_id,
        customer_name=sale.customer_name,
        customer_phone=sale.customer_phone,
        product_id=product.id,
        product_name=product.name,
        unit=product.unit,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=x_value,
        reason=reason,
        refund_type=refund_type,
        refund_amount=refund_amount,
        bonus_points=bonus_points,
        debt_reduction=debt_reduction,
        exchange_product_id=exchange_product.id if exchange_product else None,
        exchange_product_name=exchange_product.name if exchange_product else None,
        exchange_quantity=exchange_quantity if exchange_product else None,
        exchange_amount=exchange_value,
        tradein_amount=tradein_amount,
        extra_amount=extra_amount,
        warehouse=target_wh,
        status="completed",
        note=note,
        created_by=user_name,
    )
    db.add(act)

    try:
        create_system_log(
            db, user_id=user_id, user_name=user_name,
            action=f"Qaytarish: {act_number} {product.name} x {quantity} ({refund_type})",
            module="sales",
        )
    except Exception:
        pass

    db.commit()
    db.refresh(act)
    return act


def get_return_act(db: Session, act_id: int) -> Optional[models.ReturnAct]:
    return db.query(models.ReturnAct).filter(models.ReturnAct.id == act_id).first()


def list_return_acts(db: Session, limit: int = 50,
                     sale_id: int = None, customer_id: int = None) -> List[models.ReturnAct]:
    """Qaytarish aktlari ro'yxati (eng yangilari avval)"""
    q = db.query(models.ReturnAct)
    if sale_id:
        q = q.filter(models.ReturnAct.sale_id == sale_id)
    if customer_id:
        q = q.filter(models.ReturnAct.customer_id == customer_id)
    return q.order_by(models.ReturnAct.created_at.desc()).limit(limit).all()


def return_act_to_dict(act: models.ReturnAct) -> Dict:
    """Qaytarish aktini API uchun dict ko'rinishiga o'tkazish"""
    return {
        "id": act.id,
        "act_number": act.act_number,
        "sale_id": act.sale_id,
        "customer_id": act.customer_id,
        "customer_name": act.customer_name,
        "customer_phone": act.customer_phone,
        "product_id": act.product_id,
        "product_name": act.product_name,
        "unit": act.unit,
        "quantity": act.quantity,
        "unit_price": act.unit_price,
        "total_amount": act.total_amount,
        "reason": act.reason,
        "reason_label": RETURN_REASON_LABELS.get(act.reason, act.reason),
        "refund_type": act.refund_type,
        "refund_type_label": RETURN_TYPE_LABELS.get(act.refund_type, act.refund_type),
        "refund_amount": act.refund_amount or 0,
        "bonus_points": act.bonus_points or 0,
        "debt_reduction": act.debt_reduction or 0,
        "exchange_product_id": act.exchange_product_id,
        "exchange_product_name": act.exchange_product_name,
        "exchange_quantity": act.exchange_quantity,
        "exchange_amount": act.exchange_amount or 0,
        "tradein_amount": act.tradein_amount or 0,
        "extra_amount": act.extra_amount or 0,
        "warehouse": act.warehouse,
        "status": act.status,
        "note": act.note,
        "created_by": act.created_by,
        "created_at": act.created_at.isoformat() if act.created_at else None,
    }


# =============== YETKAZIB BERUVCHILAR VA QABUL AKTLARI ===============
def create_supplier(db: Session, data: Dict) -> models.Supplier:
    """Yangi yetkazib beruvchi yaratish"""
    supplier = models.Supplier(**data)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier

def get_supplier(db: Session, supplier_id: int) -> Optional[models.Supplier]:
    return db.query(models.Supplier).filter(models.Supplier.id == supplier_id).first()

def list_suppliers(db: Session, skip: int = 0, limit: int = 100) -> List[models.Supplier]:
    return db.query(models.Supplier).order_by(models.Supplier.name).offset(skip).limit(limit).all()

def update_supplier(db: Session, supplier_id: int, data: Dict) -> Optional[models.Supplier]:
    supplier = get_supplier(db, supplier_id)
    if supplier:
        for k, v in data.items():
            setattr(supplier, k, v)
        db.commit()
        db.refresh(supplier)
    return supplier


def create_supplier_delivery(db: Session, supplier_id: int, raw_material_id: int,
                             quantity_ordered: float, quantity_received: float,
                             quality_status: str = "qabul_qilingan",
                             price_per_unit: float = 0.0,
                             notes: str = None, created_by: str = None,
                             photo_path: str = None) -> models.SupplierDelivery:
    """
    Yetkazib beruvchidan tovarni qabul qilish (sifat nazorati akti).
    - Qabul qilingan qism ombor zaxirasiga qo'shiladi
    - Kamomad/rad etilgan qism yetkazib beruvchi qarziga yoziladi
    """
    supplier = get_supplier(db, supplier_id)
    material = db.query(models.RawMaterial).filter(models.RawMaterial.id == raw_material_id).first()
    if not supplier or not material:
        raise ValueError("Yetkazib beruvchi yoki xom ashyo topilmadi")

    today = datetime.now()
    act_count = db.query(models.SupplierDelivery).filter(
        extract("year", models.SupplierDelivery.created_at) == today.year,
        extract("month", models.SupplierDelivery.created_at) == today.month,
    ).count() + 1
    act_number = f"QA-{today.strftime('%Y%m')}-{act_count:04d}"

    accepted_qty = quantity_received if quality_status == "qabul_qilingan" else \
        (quantity_received * 0.5 if quality_status == "qisman" else 0)
    deficiency = quantity_ordered - accepted_qty
    deficiency_amount = max(deficiency, 0) * price_per_unit

    delivery = models.SupplierDelivery(
        act_number=act_number,
        supplier_id=supplier_id,
        raw_material_id=raw_material_id,
        quantity_ordered=quantity_ordered,
        quantity_received=quantity_received,
        quality_status=quality_status,
        price_per_unit=price_per_unit,
        deficiency_amount=deficiency_amount,
        photo_path=photo_path,
        notes=notes,
        created_by=created_by,
    )
    db.add(delivery)

    # Qabul qilingan miqdor zaxiraga qo'shiladi
    material.current_stock = (material.current_stock or 0) + accepted_qty
    material.last_purchase_date = datetime.now()
    material.supplier = supplier.name
    material.supplier_id = supplier.id

    # Rejalashtirilgan vaqtdan kech/oz kelganini baholash
    if deficiency > 0:
        supplier.total_debt = (supplier.total_debt or 0) + deficiency_amount
        supplier.late_count = (supplier.late_count or 0) + 1
    else:
        supplier.on_time_count = (supplier.on_time_count or 0) + 1
    supplier.rating = round(
        (supplier.on_time_count * 5 + supplier.late_count * 1) /
        max(supplier.on_time_count + supplier.late_count, 1), 1
    )

    db.add(models.WarehouseTransaction(
        raw_material_id=raw_material_id,
        quantity=accepted_qty,
        transaction_type=models.TransactionType.INCOME,
        user_id=0,
        user_name=created_by or "Tizim",
        document_number=act_number,
        counterparty=supplier.name,
        notes=f"Qabul akti: {act_number} ({quality_status})",
    ))
    db.commit()
    db.refresh(delivery)
    return delivery


def get_supplier_reorder_suggestions(db: Session) -> List[Dict]:
    """Minimal zaxiradan pastga tushgan xom ashyolar uchun avtomatik buyurtma tavsiyasi"""
    low_materials = db.query(models.RawMaterial).filter(
        models.RawMaterial.current_stock <= models.RawMaterial.min_stock
    ).all()

    suggestions = []
    for mat in low_materials:
        suggestions.append({
            "raw_material_id": mat.id,
            "raw_material_name": mat.name,
            "unit": mat.unit,
            "current_stock": mat.current_stock,
            "min_stock": mat.min_stock,
            "suggested_order": max(mat.min_stock * 2 - mat.current_stock, mat.min_stock),
            "supplier_name": mat.supplier or "Noma'lum",
            "supplier_id": mat.supplier_id,
        })
    return suggestions


def supplier_to_dict(supplier: models.Supplier) -> Dict:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "phone": supplier.phone,
        "contact_person": supplier.contact_person,
        "address": supplier.address,
        "rating": supplier.rating or 5.0,
        "on_time_count": supplier.on_time_count or 0,
        "late_count": supplier.late_count or 0,
        "total_debt": supplier.total_debt or 0,
        "notes": supplier.notes,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None,
    }


# =============== O'LCHOV BIRLIKLARI KONVERTATSIYASI ===============
def add_product_unit(db: Session, product_id: int, unit: str, factor: float,
                     base_unit: str, price: float = None) -> models.ProductUnit:
    """Mahsulotga qo'shimcha o'lchov birligi qo'shish (1 pallet = 40 qop = 2000 kg)"""
    existing = db.query(models.ProductUnit).filter(
        models.ProductUnit.product_id == product_id,
        models.ProductUnit.unit == unit,
    ).first()
    if existing:
        existing.factor = factor
        existing.base_unit = base_unit
        existing.price = price
        db.commit()
        db.refresh(existing)
        return existing
    pu = models.ProductUnit(
        product_id=product_id, unit=unit, factor=factor,
        base_unit=base_unit, price=price,
    )
    db.add(pu)
    db.commit()
    db.refresh(pu)
    return pu


def get_product_units(db: Session, product_id: int) -> List[models.ProductUnit]:
    """Mahsulotning barcha o'lchov birliklari"""
    return db.query(models.ProductUnit).filter(
        models.ProductUnit.product_id == product_id
    ).all()


def convert_quantity(db: Session, product_id: int, from_unit: str, qty: float,
                     to_unit: str) -> Optional[Dict]:
    """
    Bir o'lchov birligidan boshqasiga o'tkazish.
    Masalan: 1 pallet = 40 qop, 1 qop = 50 kg -> 2 pallet = 80 qop = 4000 kg
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        return None
    units = get_product_units(db, product_id)
    unit_map = {u.unit: u for u in units}
    # Asosiy birlik ham har doim bor: product.unit factor=1
    if product.unit not in unit_map:
        unit_map[product.unit] = models.ProductUnit(
            unit=product.unit, factor=1.0, base_unit=product.unit
        )

    f = unit_map.get(from_unit)
    t = unit_map.get(to_unit)
    if not f or not t:
        return {"error": "Bunday birlik topilmadi", "available": list(unit_map.keys())}

    base_qty = qty * f.factor
    converted = base_qty / t.factor if t.factor else 0
    return {
        "product_id": product_id,
        "product_name": product.name,
        "from": from_unit,
        "to": to_unit,
        "quantity": qty,
        "base_quantity": base_qty,
        "result": converted,
    }


# =============== REZERVATSIYA ===============
def get_available_product_qty(db: Session, product_id: int) -> float:
    """Mahsulotning sotuvga tayyor qoldig'i
    (ishlab chiqarilgan + qaytarilgan - sotilgan - faol rezerv)"""
    produced = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0)).filter(
        models.WarehouseTransaction.product_id == product_id,
        models.WarehouseTransaction.transaction_type == models.TransactionType.PRODUCTION,
    ).scalar() or 0
    adjusted = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0)).filter(
        models.WarehouseTransaction.product_id == product_id,
        models.WarehouseTransaction.transaction_type == models.TransactionType.INVENTORY,
    ).scalar() or 0
    sold = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0)).filter(
        models.WarehouseTransaction.product_id == product_id,
        models.WarehouseTransaction.transaction_type == models.TransactionType.SALE,
    ).scalar() or 0
    returned = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0)).filter(
        models.WarehouseTransaction.product_id == product_id,
        models.WarehouseTransaction.transaction_type == models.TransactionType.RETURN,
    ).scalar() or 0
    reserved = db.query(func.coalesce(func.sum(models.Reservation.quantity), 0)).filter(
        models.Reservation.product_id == product_id,
        models.Reservation.status == "faol",
    ).scalar() or 0
    return (produced + returned - sold - reserved + adjusted)


def create_reservation(db: Session, product_id: int, quantity: float,
                       expires_in_hours: float = 2.0,
                       customer_id: int = None, customer_name: str = None,
                       customer_phone: str = None, notes: str = None,
                       created_by: str = None) -> Dict:
    """Mahsulotni vaqtincha bloklash (2-24 soat), muddati tugasa avtomatik yechiladi"""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        return {"error": "Mahsulot topilmadi"}
    if quantity is None or quantity <= 0:
        return {"error": "Miqdor 0 dan katta bo'lishi kerak"}
    available = get_available_product_qty(db, product_id)
    if available < quantity:
        return {"error": f"Omborda yetarli emas (mavjud: {available:,.0f} {product.unit})"}

    reservation = models.Reservation(
        reservation_code=f"RSV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        product_id=product_id,
        quantity=quantity,
        customer_id=customer_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        status="faol",
        expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
        notes=notes,
        created_by=created_by,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return {"reservation": reservation, "expires_at": reservation.expires_at}


def release_expired_reservations(db: Session) -> int:
    """Muddati tugagan rezervatsiyalarni avtomatik bo'shatish"""
    now = datetime.utcnow()
    expired = db.query(models.Reservation).filter(
        models.Reservation.status == "faol",
        models.Reservation.expires_at < now,
    ).all()
    for r in expired:
        r.status = "yechilgan"
    if expired:
        db.commit()
    return len(expired)


def list_active_reservations(db: Session, limit: int = 50) -> List[models.Reservation]:
    release_expired_reservations(db)
    return db.query(models.Reservation).order_by(models.Reservation.created_at.desc()).limit(limit).all()


def complete_reservation(db: Session, reservation_id: int) -> bool:
    r = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if r and r.status == "faol":
        r.status = "yakunlangan"
        db.commit()
        return True
    return False


def cancel_reservation(db: Session, reservation_id: int) -> bool:
    r = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
    if r and r.status == "faol":
        r.status = "bekor_qilingan"
        db.commit()
        return True
    return False


# =============== OMBORLARARO KO'CHIRISH ===============
def create_transfer(db: Session, item_type: str, item_id: int, quantity: float,
                    source_warehouse: str, target_warehouse: str,
                    notes: str = None, user_id: int = 0, user_name: str = None) -> Dict:
    """
    Omborlararo ko'chirish akti. Masalan: zavod -> ombor, ombor -> do'kon, brak -> qayta ishlash
    item_type: 'raw' (xom ashyo) yoki 'product' (tayyor mahsulot)
    """
    if item_type == "raw":
        item = db.query(models.RawMaterial).filter(models.RawMaterial.id == item_id).first()
    else:
        item = db.query(models.Product).filter(models.Product.id == item_id).first()
    if not item:
        return {"error": "Mahsulot/xom ashyo topilmadi"}
    if quantity is None or quantity <= 0:
        return {"error": "Miqdor 0 dan katta bo'lishi kerak"}
    if item_type == "raw" and (item.current_stock or 0) < quantity:
        return {"error": f"Xom ashyo yetarli emas (mavjud: {item.current_stock:,.0f})"}
    if item_type != "raw":
        available = get_available_product_qty(db, item_id)
        if available < quantity:
            return {"error": f"Tayyor mahsulot yetarli emas (mavjud: {available:,.0f} {item.unit})"}

    transfer = models.WarehouseTransaction(
        product_id=None if item_type == "raw" else item_id,
        raw_material_id=item_id if item_type == "raw" else None,
        quantity=quantity,
        transaction_type=models.TransactionType.TRANSFER,
        user_id=user_id,
        user_name=user_name or "Tizim",
        source_warehouse=source_warehouse,
        target_warehouse=target_warehouse,
        notes=notes,
    )
    db.add(transfer)
    if item_type == "raw":
        item.warehouse = target_warehouse
        item.sector = notes or None
    else:
        item.warehouse = target_warehouse
        item.sector = notes or None
    db.commit()
    return {"transfer": transfer}


def list_transfers(db: Session, limit: int = 100) -> List[models.WarehouseTransaction]:
    return db.query(models.WarehouseTransaction).filter(
        models.WarehouseTransaction.transaction_type == models.TransactionType.TRANSFER
    ).order_by(models.WarehouseTransaction.created_at.desc()).limit(limit).all()


# =============== INVENTARIZATSIYA ===============
def create_inventory_check(db: Session, warehouse: str, item_type: str, item_id: int,
                           actual_quantity: float, reason: str = None,
                           notes: str = None, created_by: str = None) -> models.InventoryCheck:
    """
    Inventarizatsiya varaqasi: tizimdagi qoldiq bilan sanab chiqilgan miqdorni solishtiradi.
    Farq bo'lsa yetishmovchilik dalolatnomasi tayyorlanadi (act_created=True).
    """
    if item_type == "raw":
        item = db.query(models.RawMaterial).filter(models.RawMaterial.id == item_id).first()
        system_qty = item.current_stock if item else 0
        mat_id, prod_id = item_id, None
    else:
        item = db.query(models.Product).filter(models.Product.id == item_id).first()
        system_qty = get_available_product_qty(db, item_id)
        mat_id, prod_id = None, item_id

    if not item:
        raise ValueError("Element topilmadi")

    check = models.InventoryCheck(
        check_number=f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        warehouse=warehouse,
        raw_material_id=mat_id,
        product_id=prod_id,
        system_quantity=system_qty,
        actual_quantity=actual_quantity,
        difference=actual_quantity - system_qty,
        reason=reason or ("Yetishmovchilik" if actual_quantity < system_qty else "Ortiqcha"),
        act_created=abs(actual_quantity - system_qty) > 0.001,
        notes=notes,
        created_by=created_by,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def list_inventory_checks(db: Session, limit: int = 100) -> List[models.InventoryCheck]:
    return db.query(models.InventoryCheck).order_by(models.InventoryCheck.created_at.desc()).limit(limit).all()


# =============== MOLIYA: P&L, SOLIQ, QARZLAR ===============
def _day_end(day: date) -> datetime:
    """Kun oxirini qaytaradi — sana bo'yicha filter kunni to'liq qamrab oladi"""
    return datetime.combine(day, datetime.min.time()) + timedelta(days=1) - timedelta(seconds=1)


def get_pl_report(db: Session, start_date: date, end_date: date) -> Dict:
    """Foyda/Zarar hisoboti (P&L) — daromad, tannarx, xarajat, sof foyda"""
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = _day_end(end_date)

    sales = db.query(models.Sale).filter(
        models.Sale.sale_date >= start_dt,
        models.Sale.sale_date <= end_dt,
    ).all()

    revenue = sum(s.total_amount for s in sales)
    discounts = sum(s.discount_amount or 0 for s in sales)

    # Qaytarish aktlari (davrda): mijozga qaytarilgan pullar + omborga qaytgan tovar tannarxi
    acts = db.query(models.ReturnAct).filter(
        models.ReturnAct.created_at >= start_dt,
        models.ReturnAct.created_at <= end_dt,
        models.ReturnAct.status != "cancelled",
    ).all()
    refunds = sum(a.refund_amount or 0 for a in acts)

    # Sotilgan mahsulot tannarxi
    cogs = 0.0
    for s in sales:
        prod = db.query(models.Product).filter(models.Product.id == s.product_id).first()
        if prod:
            cogs += (prod.production_cost or 0) * s.quantity

    # Qaytarilgan tovar omborga qaytgani uchun tannarx ham qaytariladi
    for a in acts:
        prod = db.query(models.Product).filter(models.Product.id == a.product_id).first()
        if prod:
            cogs -= (prod.production_cost or 0) * a.quantity

    # Ishlab chiqarish buyurtmalari tannarxi (davrda)
    po_cost = db.query(func.sum(models.ProductionOrder.total_cost)).filter(
        models.ProductionOrder.created_at >= start_dt,
        models.ProductionOrder.created_at <= end_dt,
    ).scalar() or 0

    # Maosh xarajati
    salary = db.query(func.sum(models.SalaryPayment.total_amount)).filter(
        models.SalaryPayment.payment_date >= start_dt,
        models.SalaryPayment.payment_date <= end_dt,
        models.SalaryPayment.status == "paid",
    ).scalar() or 0

    # Eslatma: Sale.total_amount allaqachon chegirmadan keyingi (net) qiymat.
    # 'discounts' alohida tahliliy ko'rsatkich sifatida qaytariladi, qayta ayrilmaydi.
    expenses = po_cost + salary
    gross_profit = revenue - refunds - cogs
    net_profit = gross_profit - expenses

    return {
        "period": [start_date.isoformat(), end_date.isoformat()],
        "revenue": round(revenue, 2),
        "refunds": round(refunds, 2),
        "discounts": round(discounts, 2),
        "cogs": round(cogs, 2),
        "production_cost": round(po_cost, 2),
        "salary_cost": round(salary, 2),
        "total_expenses": round(expenses, 2),
        "gross_profit": round(gross_profit, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin": round(net_profit / revenue * 100, 1) if revenue else 0,
    }


def calculate_tax(amount: float, tax_rate: float = 12.0) -> Dict:
    """QQS (12%) va aylanma soliq (4%) hisoblash"""
    qqs = amount * tax_rate / 100
    return {
        "amount": round(amount, 2),
        "rate": tax_rate,
        "qqs": round(qqs, 2),
        "net": round(amount - qqs, 2),
    }


def get_customer_debts_report(db: Session) -> Dict:
    """Barcha mijozlar qarzi (debitorlik) — jami, kechiktirilgan, to'lanmagan"""
    customers = db.query(models.Customer).filter(
        models.Customer.total_debt > 0
    ).order_by(models.Customer.total_debt.desc()).all()

    today = datetime.utcnow().date()
    overdue_list = []
    total_debt = 0.0
    for c in customers:
        total_debt += c.total_debt or 0
        # Kechiktirilgan sotuvlar
        overdue_count = db.query(models.Sale).filter(
            models.Sale.customer_id == c.id,
            models.Sale.is_credit == True,
            models.Sale.credit_status != models.CreditStatus.PAID.value,
            models.Sale.due_date < datetime.combine(today, datetime.min.time()),
        ).count()
        if overdue_count:
            overdue_list.append({"customer": c.name, "debt": c.total_debt, "overdue_count": overdue_count})

    return {
        "total_debt": round(total_debt, 2),
        "debtor_count": len(customers),
        "overdue_count": len(overdue_list),
        "overdue_list": overdue_list,
    }


def get_credit_sales(db: Session, status: str = None, limit: int = 100) -> List[models.Sale]:
    """Nasiya sotuvlari ro'yxati (status: tolanmagan/qisman/toliq_tolangan/muddati_otgan)"""
    query = db.query(models.Sale).filter(models.Sale.is_credit == True)
    if status == "muddati_otgan":
        today = datetime.utcnow()
        query = query.filter(
            models.Sale.credit_status != models.CreditStatus.PAID.value,
            models.Sale.due_date < today,
        )
    elif status:
        query = query.filter(models.Sale.credit_status == status)
    return query.order_by(models.Sale.sale_date.desc()).limit(limit).all()


# =============== YETKAZIB BERISH (DELIVERY) — haydovchi + GPS kuzatuv ===============
DELIVERY_STATUS_LABELS = {
    "tayinlangan": "📋 Tayinlangan",
    "yo'lda": "🚚 Yo'lda",
    "yetkazildi": "✅ Yetkazildi",
    "bekor": "❌ Bekor qilingan",
}


def get_sale_delivery_remaining(db: Session, sale: models.Sale) -> float:
    """Sotuv bo'yicha hali yetkazilmagan miqdor (qaytarilganlar hisobga olinadi)"""
    delivered = db.query(func.coalesce(func.sum(models.Delivery.quantity), 0)).filter(
        models.Delivery.sale_id == sale.id,
        models.Delivery.status.in_(["yetkazildi", "yo'lda"]),
    ).scalar() or 0
    return max((sale.quantity or 0) - (sale.returned_qty or 0) - delivered, 0)


def get_active_delivery_for_sale(db: Session, sale_id: int):
    """Sotuv uchun faol (bekor bo'lmagan) yetkazish topshirig'i"""
    return db.query(models.Delivery).filter(
        models.Delivery.sale_id == sale_id,
        models.Delivery.status != "bekor",
    ).first()


def list_deliverable_sales(db: Session, limit: int = 20) -> List[models.Sale]:
    """Yetkazish topshirig'i yaratish mumkin bo'lgan sotuvlar (qoldiq bor, faol topshiriq yo'q)"""
    sales = db.query(models.Sale).order_by(models.Sale.sale_date.desc()).limit(limit * 3).all()
    result = []
    for s in sales:
        if s.status in ("qaytarilgan", "yetkazib_berildi"):
            continue
        if get_sale_delivery_remaining(db, s) <= 0:
            continue
        if get_active_delivery_for_sale(db, s.id):
            continue
        result.append(s)
        if len(result) >= limit:
            break
    return result


def create_delivery(db: Session, *, sale_id: int, driver_id: int,
                    quantity: float = None, address: str = None,
                    note: str = None, created_by: str = None) -> models.Delivery:
    """
    Sotuv uchun yetkazish topshirig'i yaratish va haydovchiga biriktirish.
    - Sotuvda yetkazilmagan qoldiq bo'lishi kerak
    - Shu sotuv uchun faol topshiriq bo'lmasligi kerak
    - Haydovchi rolidagi faol xodim tanlanishi kerak
    """
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise ValueError("Sotuv topilmadi")

    remaining = get_sale_delivery_remaining(db, sale)
    if remaining <= 0:
        raise ValueError("Bu sotuvda yetkaziladigan qoldiq yo'q")
    if get_active_delivery_for_sale(db, sale.id):
        raise ValueError("Bu sotuv uchun allaqachon faol yetkazish topshirig'i bor")

    driver = db.query(models.Employee).filter(models.Employee.id == driver_id).first() if driver_id else None
    if not driver:
        raise ValueError("Haydovchi topilmadi")
    if driver.role != "haydovchi":
        raise ValueError("Tanlangan xodim haydovchi emas")
    active = models.EmployeeStatus.ACTIVE
    if not (driver.status == active or str(driver.status) in (active.name, active.value)):
        raise ValueError("Haydovchi faol emas (ishlamayapti)")

    product = db.query(models.Product).filter(models.Product.id == sale.product_id).first()
    customer = db.query(models.Customer).filter(models.Customer.id == sale.customer_id).first() if sale.customer_id else None

    qty = float(quantity) if quantity else remaining
    if qty <= 0 or qty > remaining + 1e-9:
        raise ValueError(f"Yetkaziladigan miqdor noto'g'ri (qoldiq: {remaining:,.0f})")

    now = datetime.now()
    d_count = db.query(models.Delivery).filter(
        extract("year", models.Delivery.created_at) == now.year,
        extract("month", models.Delivery.created_at) == now.month,
    ).count() + 1
    number = f"DLV-{now.strftime('%Y%m')}-{d_count:04d}"

    delivery = models.Delivery(
        delivery_number=number,
        sale_id=sale.id,
        customer_id=sale.customer_id,
        customer_name=sale.customer_name,
        customer_phone=sale.customer_phone,
        customer_address=address or (customer.address if customer else None) or sale.customer_name,
        product_id=product.id if product else sale.product_id,
        product_name=product.name if product else "Noma'lum",
        unit=product.unit if product else "",
        quantity=qty,
        driver_id=driver.id,
        driver_name=driver.full_name,
        status="tayinlangan",
        note=note,
        created_by=created_by,
    )
    db.add(delivery)
    try:
        create_system_log(db, user_name=created_by,
                          action=f"Yetkazish: {number} -> {driver.full_name} ({sale.customer_name})",
                          module="delivery")
    except Exception:
        pass
    db.commit()
    db.refresh(delivery)
    return delivery


def get_delivery(db: Session, delivery_id: int) -> Optional[models.Delivery]:
    return db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()


def list_deliveries(db: Session, driver_id: int = None, status: str = None,
                    limit: int = 50) -> List[models.Delivery]:
    """Yetkazishlar ro'yxati (haydovchi/holat bo'yicha filterlash mumkin)"""
    q = db.query(models.Delivery)
    if driver_id:
        q = q.filter(models.Delivery.driver_id == driver_id)
    if status:
        q = q.filter(models.Delivery.status == status)
    return q.order_by(models.Delivery.created_at.desc()).limit(limit).all()


def start_delivery(db: Session, delivery_id: int) -> models.Delivery:
    """Yetkazishni boshlash (yo'lda) — GPS kuzatuvga tayyor"""
    delivery = get_delivery(db, delivery_id)
    if not delivery:
        raise ValueError("Yetkazish topilmadi")
    if delivery.status in ("yetkazildi", "bekor"):
        raise ValueError("Yakunlangan yetkazishni boshlab bo'lmaydi")
    delivery.status = "yo'lda"
    delivery.started_at = delivery.started_at or datetime.utcnow()
    db.commit()
    db.refresh(delivery)
    return delivery


def record_delivery_location(db: Session, delivery_id: int, latitude: float,
                             longitude: float, accuracy: float = None,
                             source: str = "api") -> models.DeliveryLocation:
    """Haydovchi GPS nuqtasini qayd qilish (avtomatik 'yo'lda' holatiga o'tkazadi)"""
    delivery = get_delivery(db, delivery_id)
    if not delivery:
        raise ValueError("Yetkazish topilmadi")
    if delivery.status in ("yetkazildi", "bekor"):
        raise ValueError("Yakunlangan yetkazishda joylashuv qayd etilmaydi")
    if delivery.status == "tayinlangan":
        start_delivery(db, delivery_id)
        delivery = get_delivery(db, delivery_id)

    if delivery.start_lat is None:
        delivery.start_lat = latitude
        delivery.start_lng = longitude
    delivery.current_lat = latitude
    delivery.current_lng = longitude
    delivery.last_location_at = datetime.utcnow()

    point = models.DeliveryLocation(
        delivery_id=delivery.id,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        source=source,
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return point


def complete_delivery(db: Session, delivery_id: int, note: str = None) -> models.Delivery:
    """Yetkazib berishni yakunlash — sotuv 'yetkazib_berildi' holatiga o'tadi"""
    delivery = get_delivery(db, delivery_id)
    if not delivery:
        raise ValueError("Yetkazish topilmadi")
    if delivery.status == "yetkazildi":
        return delivery
    if delivery.status == "bekor":
        raise ValueError("Bekor qilingan yetkazishni yakunlab bo'lmaydi")
    if delivery.status == "tayinlangan":
        delivery.started_at = datetime.utcnow()
    delivery.status = "yetkazildi"
    delivery.delivered_at = datetime.utcnow()
    if note:
        delivery.note = note

    sale = db.query(models.Sale).filter(models.Sale.id == delivery.sale_id).first()
    if sale and sale.status == "completed":
        sale.status = "yetkazib_berildi"
    db.commit()
    db.refresh(delivery)
    return delivery


def cancel_delivery(db: Session, delivery_id: int, note: str = None) -> models.Delivery:
    """Yetkazishni bekor qilish"""
    delivery = get_delivery(db, delivery_id)
    if not delivery:
        raise ValueError("Yetkazish topilmadi")
    if delivery.status in ("yetkazildi", "bekor"):
        raise ValueError("Bu yetkazish allaqachon yakunlangan/bekor qilingan")
    delivery.status = "bekor"
    delivery.cancelled_at = datetime.utcnow()
    if note:
        delivery.note = note
    db.commit()
    db.refresh(delivery)
    return delivery


def delivery_to_dict(delivery: models.Delivery) -> Dict:
    """Yetkazishni API uchun dict ko'rinishiga o'tkazish"""
    def _dt(value):
        return value.isoformat() if value else None
    return {
        "id": delivery.id,
        "delivery_number": delivery.delivery_number,
        "sale_id": delivery.sale_id,
        "customer_id": delivery.customer_id,
        "customer_name": delivery.customer_name,
        "customer_phone": delivery.customer_phone,
        "customer_address": delivery.customer_address,
        "product_id": delivery.product_id,
        "product_name": delivery.product_name,
        "unit": delivery.unit,
        "quantity": delivery.quantity,
        "driver_id": delivery.driver_id,
        "driver_name": delivery.driver_name,
        "status": delivery.status,
        "status_label": DELIVERY_STATUS_LABELS.get(delivery.status, delivery.status),
        "start_lat": delivery.start_lat,
        "start_lng": delivery.start_lng,
        "current_lat": delivery.current_lat,
        "current_lng": delivery.current_lng,
        "last_location_at": _dt(delivery.last_location_at),
        "assigned_at": _dt(delivery.assigned_at),
        "started_at": _dt(delivery.started_at),
        "delivered_at": _dt(delivery.delivered_at),
        "cancelled_at": _dt(delivery.cancelled_at),
        "note": delivery.note,
        "created_by": delivery.created_by,
        "created_at": _dt(delivery.created_at),
    }


def list_delivery_locations(db: Session, delivery_id: int, limit: int = 200) -> List[models.DeliveryLocation]:
    """Yetkazish GPS nuqtalari (eng eskisidan yangisiga)"""
    return db.query(models.DeliveryLocation).filter(
        models.DeliveryLocation.delivery_id == delivery_id
    ).order_by(models.DeliveryLocation.recorded_at.asc()).limit(limit).all()


# =============== NASIYA QARZ SMS ESLATMALARI ===============
def sale_outstanding_amount(sale: models.Sale) -> float:
    """Sotuv bo'yicha qolgan qarz (qaytarilganlar hisobga olinadi)"""
    return max((sale.total_amount or 0) - (sale.paid_amount or 0) - (sale.returned_amount or 0), 0)


def get_debt_reminder_candidates(db: Session, overdue_days: int,
                                 limit: int = 200) -> List[models.Sale]:
    """
    Muddati o'tgan va hali shu kun oralig'ida SMS eslatma olmagan nasiya sotuvlar.
    - due_date + overdue_days <= hozirgi vaqt (kunlar yetdi)
    - credit_status != toliq_tolangan va qoldiq qarz > 0
    - (sale_id, overdue_days) uchun DebtReminder yozuvi yo'q
    """
    threshold = datetime.utcnow() - timedelta(days=overdue_days)
    already = db.query(models.DebtReminder.sale_id).filter(
        models.DebtReminder.day_bucket == overdue_days
    )
    sales = db.query(models.Sale).filter(
        models.Sale.is_credit == True,
        models.Sale.credit_status != models.CreditStatus.PAID.value,
        models.Sale.due_date.isnot(None),
        models.Sale.due_date <= threshold,
        ~models.Sale.id.in_(already),
    ).order_by(models.Sale.due_date.asc()).limit(limit).all()
    return [s for s in sales if sale_outstanding_amount(s) > 0]


def mark_debt_reminder_sent(db: Session, sale_id: int, day_bucket: int,
                            status: str = "sent", error: str = None) -> models.DebtReminder:
    """SMS eslatma yuborilganini qayd qilish (sale_id + day_bucket unikal).
    Takror yuborilmasligi uchun: mavjud bo'lsa shunchaki qaytariladi.
    """
    row = db.query(models.DebtReminder).filter(
        models.DebtReminder.sale_id == sale_id,
        models.DebtReminder.day_bucket == day_bucket,
    ).first()
    if row:
        return row
    row = models.DebtReminder(
        sale_id=sale_id,
        day_bucket=day_bucket,
        status=status,
        error=error,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# =============== SEKIN SOTILADIGAN ZAXIRA (SLOW-MOVING STOCK) ===============
def item_last_movement(db: Session, item_type: str, item_id: int) -> Optional[datetime]:
    """Tovar (product) yoki xom ashyo (raw) uchun oxirgi ombor harakati vaqti.

    Barcha harakat turlari hisobga olinadi: ishlab chiqarish, sotuv, kirim
    (qabul akti), qaytarish, ko'chirish, inventarizatsiya.
    """
    if item_type == "raw":
        q = db.query(func.max(models.WarehouseTransaction.date)).filter(
            models.WarehouseTransaction.raw_material_id == item_id
        )
    else:
        q = db.query(func.max(models.WarehouseTransaction.date)).filter(
            models.WarehouseTransaction.product_id == item_id
        )
    return q.scalar()


def slow_stock_alerted_ids(db: Session, item_type: str) -> set:
    """Yuborilgan (sent) ogohlantirishga ega tovarlar ID'lari — qayta yubormaslik uchun.
    (failed qaydlar qayta uriniladi, shuning uchun hisobga olinmaydi.)"""
    rows = db.query(models.SlowStockAlert.item_id).filter(
        models.SlowStockAlert.item_type == item_type,
        models.SlowStockAlert.status == "sent",
    ).all()
    return {r[0] for r in rows}


def get_slow_moving_products(db: Session, days: int = 30,
                             limit: int = 100) -> List[Dict]:
    """Tayyor mahsulotlar: omborda qoldig'i bor va `days` kundan beri hech qanday
    harakat bo'lmagan. Eng uzoq harakatsiz turganlar birinchi o'rinda.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    alerted = slow_stock_alerted_ids(db, "product")
    cands = []
    for p in db.query(models.Product).filter(models.Product.is_active == True).all():  # noqa: E712
        if p.id in alerted:
            continue
        available = get_available_product_qty(db, p.id)
        if available <= 0:
            continue
        last = item_last_movement(db, "product", p.id)
        if last is None or last > cutoff:
            continue
        cands.append({
            "item_type": "product",
            "item_id": p.id,
            "name": p.name,
            "unit": p.unit,
            "quantity": round(available, 2),
            "value": round(available * (p.selling_price or 0), 0),
            "last_moved_at": last,
            "days_unmoved": (datetime.utcnow() - last).days,
        })
    cands.sort(key=lambda c: c["last_moved_at"])
    return cands[:limit]


def get_slow_moving_raw_materials(db: Session, days: int = 30,
                                  limit: int = 100) -> List[Dict]:
    """Xom ashyolar: omborda qoldig'i bor va `days` kundan beri harakatlanmagan.
    (Hech qachon harakat yozuvi bo'lmagan, lekin qoldig'i bor materiallar ham kiradi.)"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    alerted = slow_stock_alerted_ids(db, "raw")
    cands = []
    for m in db.query(models.RawMaterial).all():
        if m.id in alerted:
            continue
        if (m.current_stock or 0) <= 0:
            continue
        last = item_last_movement(db, "raw", m.id)
        if last is not None and last > cutoff:
            continue
        cands.append({
            "item_type": "raw",
            "item_id": m.id,
            "name": m.name,
            "unit": m.unit,
            "quantity": round(m.current_stock or 0, 2),
            "value": round((m.current_stock or 0) * (m.price_per_unit or 0), 0),
            "last_moved_at": last,
            "days_unmoved": (datetime.utcnow() - last).days if last else days,
        })
    cands.sort(key=lambda c: c["last_moved_at"] is None or c["last_moved_at"])
    return cands[:limit]


def mark_slow_stock_alerted(db: Session, item_type: str, item_id: int,
                            days_unmoved: int, last_moved_at: Optional[datetime] = None,
                            status: str = "sent", error: str = None) -> models.SlowStockAlert:
    """Ogohlantirish yuborilganini qayd qilish ((item_type, item_id) unikal).
    Mavjud qayd bo'lsa yangilanadi (failed -> sent holatga o'tish uchun).
    """
    row = db.query(models.SlowStockAlert).filter(
        models.SlowStockAlert.item_type == item_type,
        models.SlowStockAlert.item_id == item_id,
    ).first()
    if row is None:
        row = models.SlowStockAlert(
            item_type=item_type,
            item_id=item_id,
            status=status,
            error=error,
            days_unmoved=days_unmoved,
            last_moved_at=last_moved_at,
        )
        db.add(row)
    else:
        row.status = status
        row.error = error
        row.days_unmoved = days_unmoved
        row.last_moved_at = last_moved_at
        row.alert_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def clear_moved_slow_stock_alerts(db: Session, days: int = 30) -> int:
    """Harakatga qaytgan tovarlarning ogohlantirish qaydini o'chirish.
    Tovar yana `days` kun jim tursa qayta ogohlantiriladi.

    Returns:
        int: O'chirilgan qaydlar soni
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = db.query(models.SlowStockAlert).all()
    removed = 0
    for row in rows:
        last = item_last_movement(db, row.item_type, row.item_id)
        if last is not None and last > cutoff:
            db.delete(row)
            removed += 1
    if removed:
        db.commit()
    return removed


# =============== WEB-DO'KON (SHOP: catalog -> savat -> checkout) ===============
SHOP_ORDER_STATUS_LABELS = {
    "kutilmoqda": "⏳ To'lov kutilmoqda",
    "yakunlangan": "✅ Yakunlangan",
    "bekor_qilingan": "❌ Bekor qilingan",
}
SHOP_METHOD_LABELS = {
    "cash": "Naqd",
    "click": "Click",
    "payme": "Payme",
    "mixed": "Karta + Naqd",
}


def _new_shop_order_number(db: Session) -> str:
    """SHOP-YYYYMMDD-NNNN formatida yagona buyurtma raqami"""
    now = datetime.now()
    count = db.query(models.ShopOrder).filter(
        extract("year", models.ShopOrder.created_at) == now.year,
        extract("month", models.ShopOrder.created_at) == now.month,
        extract("day", models.ShopOrder.created_at) == now.day,
    ).count() + 1
    return f"SHOP-{now.strftime('%Y%m%d')}-{count:04d}"


def _shop_phone(raw: str) -> str:
    """Telefon raqamini soddalashtirish (probel/chiziqchalarni olib tashlash)"""
    return "".join(ch for ch in (raw or "") if ch.isdigit() or ch == "+").strip()


def _find_or_create_shop_customer(db: Session, name: str, phone: str) -> models.Customer:
    """Web-do'kondan mijozni topadi yoki ro'yxatga oladi (CRM + ballar uchun)"""
    phone = _shop_phone(phone)
    customer = db.query(models.Customer).filter(models.Customer.phone == phone).first()
    if not customer:
        customer = models.Customer(name=(name or "Do'kon mijoz")[:100], phone=phone or None,
                                   status="faol")
        db.add(customer)
        db.commit()
        db.refresh(customer)
    return customer


def _validate_shop_items(db: Session, items: list) -> List[Dict]:
    """Savatni tekshiradi: faol mahsulot + zaxirada yetarli miqdor"""
    if not items:
        raise ValueError("Savat bo'sh — mahsulot qo'shing")
    merged: Dict[int, float] = {}
    for it in items:
        try:
            pid = int(it.get("product_id") or 0)
            qty = float(it.get("quantity") or 0)
        except (TypeError, ValueError):
            raise ValueError("Noto'g'ri mahsulot yoki miqdor")
        if pid <= 0 or qty <= 0:
            raise ValueError("Noto'g'ri mahsulot yoki miqdor")
        merged[pid] = merged.get(pid, 0) + qty

    rows = []
    for pid, qty in merged.items():
        product = db.query(models.Product).filter(
            models.Product.id == pid,
            models.Product.is_active == True,
        ).first()
        if not product:
            raise ValueError("Mahsulot topilmadi (faol emas)")
        available = get_available_product_qty(db, pid)
        if qty > available:
            raise ValueError(
                f"{product.name} uchun zaxirada yetarli tovar yo'q (mavjud: {available:,.0f} {product.unit})"
            )
        rows.append({"product": product, "quantity": qty})
    return rows


def _split_online_cash(amounts: List[float], online_total: float) -> List[tuple]:
    """Aralash to'lov: har bir qator summasini onlayn/naqd qismlarga aniq bo'lish.

    Qator summalari (amounts) va jami onlayn qism (online_total) bo'yicha
    eng katta qoldiq usulida (largest remainder) so'm aniqligida taqsimlaydi:
    sum(online_i) == online_total va har qatorda online_i + cash_i == amount_i.
    Returns: [(online_i, cash_i), ...]
    """
    total_c = int(round(sum(amounts) * 100))
    online_c = int(round(online_total * 100))
    cents = [int(round(a * 100)) for a in amounts]
    n = len(cents)
    if total_c <= 0 or online_c <= 0:
        return [(0.0, round(a, 2)) for a in amounts]

    base = [c * online_c // total_c for c in cents]
    rem = online_c - sum(base)
    if n > 1 and rem > 0:
        # Qoldiq so'm-tiyinlarni eng katta kasr qoldig'iga ega qatorlarga taqsimlash
        order_idx = sorted(range(n), key=lambda i: (cents[i] * online_c % total_c), reverse=True)
        for i in range(rem):
            base[order_idx[i % n]] += 1

    online_parts = [b / 100.0 for b in base]
    pairs = []
    for a, o in zip(amounts, online_parts):
        cash = round(a - o, 2)
        # Yaxlitlash xatosini oxirgi tiyinga qadar to'g'rilash
        if abs(round(o + cash, 2) - round(a, 2)) > 1e-9:
            cash = round(cash + (round(a, 2) - round(o + cash, 2)), 2)
        pairs.append((round(o, 2), cash))
    return pairs


def _convert_shop_order_to_sales(db: Session, order: models.ShopOrder) -> List[models.Sale]:
    """Buyurtma qatorlarini Sale sifatida yozish (ombor/moliya yagona manba).

    - cash: har bir qator naqd Sale (Payment method='cash')
    - click/payme: har bir qator to'liq onlayn to'langan Sale
    - mixed: har bir qator bo'linadi — onlayn (click/payme) + naqd qismlar
      (create_sale_record payments=... orqali bir chekda aralash to'lov)
    """
    customer = db.query(models.Customer).filter(models.Customer.id == order.customer_id).first() \
        if order.customer_id else None

    method = order.method or "cash"
    amounts = [round(it.amount or 0, 2) for it in order.items]

    if method == "mixed" and (order.online_amount or 0) > 0 and (order.cash_amount or 0) > 0:
        gateway = order.online_gateway or "click"
        pairs = _split_online_cash(amounts, order.online_amount or 0)
    else:
        pairs = None

    sales = []
    for idx, item in enumerate(order.items):
        if pairs is not None:
            online_part, cash_part = pairs[idx]
            payments = []
            if online_part > 0:
                payments.append({"method": gateway, "amount": online_part})
            if cash_part > 0:
                payments.append({"method": "cash", "amount": cash_part})
            sale = create_sale_record(
                db,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=item.amount,
                payments=payments or None,
                customer=customer,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                user_id=0,
                user_name="Web-Do'kon",
            )
        else:
            sale = create_sale_record(
                db,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_amount=item.amount,
                payment_method=method,
                customer=customer,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                user_id=0,
                user_name="Web-Do'kon",
            )
        sales.append(sale)
    return sales


def create_shop_order(db: Session, *, name: str, phone: str,
                      address: str = None, comment: str = None,
                      method: str = "cash", items: list,
                      cash_amount: float = None,
                      online_gateway: str = None) -> models.ShopOrder:
    """
    Web-do'kondan buyurtma yaratish.
    - cash: darhol yakunlanadi (naqd to'lov sifatida Sale yoziladi)
    - click/payme: 'kutilmoqda' — onlayn to'lov tasdiqlanganda yakunlanadi
    - mixed (cash_amount + online_gateway): aralash to'lov — cash_amount qismi
      yetkazishda naqd, qolgani click/payme orqali onlayn to'lanadi.
    """
    method = str(method or "cash").lower()
    if method not in ("cash", "click", "payme", "mixed"):
        raise ValueError("To'lov usuli cash/click/payme/mixed bo'lishi kerak")
    name = (name or "").strip()
    phone = _shop_phone(phone)
    if not name or not phone or len(phone) < 9:
        raise ValueError("Ism va telefon raqami to'g'ri kiritilishi shart")

    rows = _validate_shop_items(db, items)
    customer = _find_or_create_shop_customer(db, name, phone)
    total = round(sum(r["quantity"] * (r["product"].selling_price or 0) for r in rows), 2)

    # ---- To'lov qismlarini normalizatsiya qilish ----
    if cash_amount is not None:
        try:
            cash_amount = float(cash_amount)
        except (TypeError, ValueError):
            raise ValueError("Naqd qismi son bo'lishi kerak")
        cash_amount = round(max(cash_amount, 0), 2)
    else:
        cash_amount = 0.0

    if method == "cash":
        if cash_amount not in (0.0, total):
            cash_amount = total  # naqd usulida butun summa yetkazishda to'lanadi
        online_amount = 0.0
        online_gateway = None
    elif method == "mixed":
        gateway = str(online_gateway or "").lower()
        if gateway not in ("click", "payme"):
            raise ValueError("Aralash to'lov uchun online_gateway click/payme bo'lishi kerak")
        online_gateway = gateway
        if cash_amount <= 0:
            raise ValueError("Aralash to'lovda naqd qismi 0 dan katta bo'lishi kerak")
        if cash_amount >= total:
            raise ValueError(
                "Naqd qismi jami summani to'liq qoplamaydi — naqd usulini tanlang "
                "yoki naqd qismini kamaytiring"
            )
        online_amount = round(total - cash_amount, 2)
        method = "mixed"
    else:  # click / payme — to'liq onlayn
        if cash_amount > 0:
            raise ValueError(f"{method} usulida to'liq onlayn to'lanadi (naqd qismi kiritilmang)")
        cash_amount = 0.0
        online_amount = total
        online_gateway = method

    order = models.ShopOrder(
        order_number=_new_shop_order_number(db),
        customer_id=customer.id,
        customer_name=customer.name,
        customer_phone=customer.phone,
        address=address or None,
        comment=comment or None,
        method=method,
        status="kutilmoqda",
        total_amount=total,
        online_amount=online_amount,
        cash_amount=cash_amount,
        online_gateway=online_gateway,
    )
    db.add(order)
    db.flush()
    for r in rows:
        p = r["product"]
        db.add(models.ShopOrderItem(
            order_id=order.id,
            product_id=p.id,
            product_name=p.name,
            unit=p.unit,
            quantity=r["quantity"],
            unit_price=p.selling_price or 0,
            amount=round(r["quantity"] * (p.selling_price or 0), 2),
        ))
    db.commit()
    db.refresh(order)

    # Naqd (yetkazishda to'lov): darhol yakunlangan sotuv sifatida yoziladi
    if method == "cash":
        _convert_shop_order_to_sales(db, order)
        db.refresh(order)
        order.status = "yakunlangan"
        order.paid_at = datetime.utcnow()
        db.commit()
        db.refresh(order)

    try:
        create_system_log(db, user_name="Web-Do'kon",
                          action=f"Do'kon buyurtmasi: {order.order_number} {order.total_amount:,.0f} so'm ({method})",
                          module="shop")
    except Exception:
        pass
    return order


def finalize_shop_order_payment(db: Session, order_id: int, method: str,
                                invoice_id: str = None) -> models.ShopOrder:
    """Onlayn to'lov tasdiqlanganda buyurtmani yakunlash (Sale yoziladi)"""
    order = db.query(models.ShopOrder).filter(models.ShopOrder.id == order_id).first()
    if not order:
        raise ValueError("Buyurtma topilmadi")
    if order.status == "bekor_qilingan":
        raise ValueError("Buyurtma bekor qilingan")
    if order.status == "yakunlangan":
        return order  # idempotent
    # Aralash buyurtmada to'lov qismlari orderda saqlanadi — conversion ularni ishlatadi.
    _convert_shop_order_to_sales(db, order)
    db.refresh(order)
    order.status = "yakunlangan"
    order.paid_at = datetime.utcnow()
    if invoice_id:
        order.invoice_id = invoice_id
    db.commit()
    db.refresh(order)
    return order


def cancel_shop_order(db: Session, order_id: int) -> models.ShopOrder:
    """Kutilayotgan (to'lanmagan) buyurtmani bekor qilish"""
    order = db.query(models.ShopOrder).filter(models.ShopOrder.id == order_id).first()
    if not order:
        raise ValueError("Buyurtma topilmadi")
    if order.status == "yakunlangan":
        raise ValueError("Yakunlangan buyurtmani bekor qilib bo'lmaydi")
    if order.status == "bekor_qilingan":
        return order
    order.status = "bekor_qilingan"
    db.commit()
    db.refresh(order)
    return order


def get_shop_order_by_number(db: Session, order_number: str) -> Optional[models.ShopOrder]:
    return db.query(models.ShopOrder).filter(
        models.ShopOrder.order_number == str(order_number or "").strip()
    ).first()


def list_shop_orders(db: Session, status: str = None, limit: int = 100) -> List[models.ShopOrder]:
    q = db.query(models.ShopOrder)
    if status:
        q = q.filter(models.ShopOrder.status == status)
    return q.order_by(models.ShopOrder.created_at.desc()).limit(limit).all()


# =============== KASSIR SMENASI (smena yopish + naqd farq) ===============
CASH_SHIFT_STATUS_LABELS = {
    "ochiq": "🟢 Ochiq",
    "yopilgan": "🔴 Yopilgan",
}
CASH_PAYMENT_LABELS = {
    "sale": "💵 Naqd sotuv",
    "debt": "📝 Nasiya avans/qarz to'lovi",
    "refund": "↩️ Qaytarish (chiqim)",
}


def get_open_cash_shift(db: Session) -> Optional[models.CashShift]:
    """Joriy ochiq smena (bir vaqtda faqat bitta smena ochiq bo'ladi)"""
    return db.query(models.CashShift).filter(
        models.CashShift.status == "ochiq"
    ).order_by(models.CashShift.opened_at.desc()).first()


def _shift_cash_payments(db: Session, shift: models.CashShift,
                         end: datetime = None) -> List[models.Payment]:
    """Smena davomidagi naqd to'lovlar (kirim +, chiqim -)"""
    end = end or datetime.utcnow()
    return db.query(models.Payment).filter(
        models.Payment.method == "cash",
        models.Payment.created_at >= shift.opened_at,
        models.Payment.created_at <= end,
    ).order_by(models.Payment.created_at.asc()).all()


def cash_shift_summary(db: Session, shift: models.CashShift,
                       end: datetime = None) -> Dict:
    """Smena bo'yicha naqd hisob: kutilgan summa + guruhlangan harakatlar"""
    payments = _shift_cash_payments(db, shift, end=end)
    groups: Dict[str, Dict] = {}
    total = shift.opening_balance or 0
    for p in payments:
        key = p.payment_type or "sale"
        g = groups.setdefault(key, {"label": CASH_PAYMENT_LABELS.get(key, key),
                                    "count": 0, "total": 0.0})
        g["count"] += 1
        g["total"] = round((g["total"] or 0) + (p.amount or 0), 2)
        total = round(total + (p.amount or 0), 2)
    return {
        "expected_cash": round(total, 2),
        "opening_balance": shift.opening_balance or 0,
        "payment_count": len(payments),
        "groups": list(groups.values()),
    }


def create_cash_shift(db: Session, *, employee_id: int = None,
                      employee_name: str = None,
                      opening_balance: float = 0.0,
                      note: str = None) -> models.CashShift:
    """Smenani boshlash (boshlang'ich naqd bilan). Bir vaqtda bitta ochiq smena."""
    if get_open_cash_shift(db):
        raise ValueError("Avval ochiq smenani yoping (smena yopish bo'limi)")
    try:
        opening_balance = float(opening_balance or 0)
    except (TypeError, ValueError):
        raise ValueError("Boshlang'ich summa noto'g'ri")
    if opening_balance < 0:
        raise ValueError("Boshlang'ich summa manfiy bo'lishi mumkin emas")

    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first() if employee_id else None
    now = datetime.now()
    seq = db.query(models.CashShift).filter(
        extract("year", models.CashShift.opened_at) == now.year,
        extract("month", models.CashShift.opened_at) == now.month,
        extract("day", models.CashShift.opened_at) == now.day,
    ).count() + 1

    shift = models.CashShift(
        shift_number=f"SHT-{now.strftime('%Y%m%d')}-{seq:03d}",
        cashier_id=employee.id if employee else None,
        cashier_name=employee.full_name if employee else (employee_name or "Kassir"),
        opening_balance=opening_balance,
        status="ochiq",
        note=note,
        opened_at=datetime.utcnow(),
    )
    db.add(shift)
    try:
        create_system_log(db, user_id=employee_id,
                          user_name=shift.cashier_name,
                          action=f"Smena boshlandi: {shift.shift_number} (boshlang'ich {opening_balance:,.0f} so'm)",
                          module="cash_shift")
    except Exception:
        pass
    db.commit()
    db.refresh(shift)
    return shift


def close_cash_shift(db: Session, shift_id: int, actual_cash: float,
                     note: str = None) -> models.CashShift:
    """Smenani yopish: haqiqiy naqd kiritiladi, farq hisoblanadi"""
    shift = db.query(models.CashShift).filter(models.CashShift.id == shift_id).first()
    if not shift:
        raise ValueError("Smena topilmadi")
    if shift.status == "yopilgan":
        raise ValueError("Smena allaqachon yopilgan")
    try:
        actual_cash = float(actual_cash)
    except (TypeError, ValueError):
        raise ValueError("Haqiqiy summa noto'g'ri")
    if actual_cash < 0:
        raise ValueError("Haqiqiy summa manfiy bo'lishi mumkin emas")

    summary = cash_shift_summary(db, shift)
    expected = summary["expected_cash"]
    shift.actual_cash = round(actual_cash, 2)
    shift.expected_cash = round(expected, 2)
    shift.difference = round(actual_cash - expected, 2)
    shift.closed_at = datetime.utcnow()
    shift.status = "yopilgan"
    if note:
        shift.note = note
    try:
        create_system_log(db, user_name=shift.cashier_name,
                          action=f"Smena yopildi: {shift.shift_number} kutilgan {expected:,.0f} / "
                                 f"haqiqiy {actual_cash:,.0f} / farq {shift.difference:+,.0f}",
                          module="cash_shift")
    except Exception:
        pass
    db.commit()
    db.refresh(shift)
    return shift


def list_cash_shifts(db: Session, status: str = None, limit: int = 50) -> List[models.CashShift]:
    q = db.query(models.CashShift)
    if status:
        q = q.filter(models.CashShift.status == status)
    return q.order_by(models.CashShift.opened_at.desc()).limit(limit).all()


def cash_shift_to_dict(shift: models.CashShift) -> Dict:
    return {
        "id": shift.id,
        "shift_number": shift.shift_number,
        "cashier_id": shift.cashier_id,
        "cashier_name": shift.cashier_name,
        "opening_balance": shift.opening_balance or 0,
        "expected_cash": shift.expected_cash,
        "actual_cash": shift.actual_cash,
        "difference": shift.difference,
        "status": shift.status,
        "status_label": CASH_SHIFT_STATUS_LABELS.get(shift.status, shift.status),
        "note": shift.note,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
    }


def shop_order_to_dict(order: models.ShopOrder) -> Dict:
    items = []
    for it in order.items:
        items.append({
            "product_id": it.product_id,
            "product_name": it.product_name,
            "unit": it.unit,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "amount": it.amount,
        })
    method = order.method or "cash"
    if method == "mixed":
        gateway_label = SHOP_METHOD_LABELS.get(order.online_gateway or "", "Karta")
        method_label = f"{gateway_label} + Naqd"
    else:
        method_label = SHOP_METHOD_LABELS.get(method, method)
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "address": order.address,
        "comment": order.comment,
        "method": method,
        "method_label": method_label,
        "status": order.status,
        "status_label": SHOP_ORDER_STATUS_LABELS.get(order.status, order.status),
        "total_amount": order.total_amount,
        "online_amount": order.online_amount or 0,
        "cash_amount": order.cash_amount or 0,
        "online_gateway": order.online_gateway,
        "invoice_id": order.invoice_id,
        "items": items,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }

# =============== ISHLAB CHIQARISH SIFAT NAZORATI (QC) ===============
# TZ: "Chiqishda mahsulot sinovdan o'tkaziladi, natija raqamli dalolatnomaga yoziladi"
# Yetkazib beruvchi qabul akti (SupplierDelivery) uslubida — faqat qabul qilingan
# qism sotiladigan omborga kiradi, rad etilgan qism brak omboriga o'tadi.
QC_STATUS_LABELS = {
    "kutilmoqda": "⏳ Sifat nazorati kutilmoqda",
    "qabul_qilingan": "✅ Qabul qilindi",
    "qisman": "⚠️ Qisman qabul",
    "rad_etilgan": "❌ Rad etildi",
}


def get_production_order(db: Session, order_id: int) -> Optional[models.ProductionOrder]:
    """Ishlab chiqarish buyurtmasini ID bo'yicha olish"""
    return db.query(models.ProductionOrder).filter(
        models.ProductionOrder.id == order_id
    ).first()


def list_production_orders_pending_qc(db: Session, limit: int = 50) -> List[models.ProductionOrder]:
    """Sifat nazorati o'tkazilmagan tayyor buyurtmalar (eng eskilari avval).

    Buyurtma COMPLETED bo'lishi va hali biron QC akti bo'lmasligi kerak.
    """
    qc_done = db.query(models.ProductionQC.order_id)
    return db.query(models.ProductionOrder).filter(
        models.ProductionOrder.status == models.OrderStatus.COMPLETED,
        ~models.ProductionOrder.id.in_(qc_done),
    ).order_by(models.ProductionOrder.actual_end.asc(),
               models.ProductionOrder.created_at.asc()).limit(limit).all()


def create_production_qc(db: Session, *, order_id: int,
                         quality_status: str = "qabul_qilingan",
                         rejected_qty: float = None,
                         notes: str = None, photo_path: str = None,
                         created_by: str = None,
                         user_id: int = 0) -> models.ProductionQC:
    """Tayyor mahsulotga sifat nazorati aktini yozish (raqamli dalolatnoma).

    - qabul_qilingan: hammasi qabul qilinadi (rejected = 0)
    - rad_etilgan: hammasi brak (rejected = butun miqdor)
    - qisman: rejected_qty ko'rsatiladi (0 < rejected < miqdor)

    Ombordagi hisob (PRODUCTION qatorlari yig'indisi = sotiladigan qoldiq):
      +quantity (to'liq chiqim, tayyor ombor) va -rejected_qty (brak chiqim)
      -> aniq ta'sir = faqat qabul qilingan qism omborga kiradi.
    """
    order = db.query(models.ProductionOrder).filter(
        models.ProductionOrder.id == order_id
    ).first()
    if not order:
        raise ValueError("Buyurtma topilmadi")
    if order.status != models.OrderStatus.COMPLETED:
        raise ValueError("Sifat nazorati faqat tayyor (COMPLETED) buyurtmalar uchun")
    existing = db.query(models.ProductionQC).filter(
        models.ProductionQC.order_id == order_id
    ).first()
    if existing:
        raise ValueError(f"Bu buyurtma uchun sifat nazorati o'tkazilgan ({existing.act_number})")

    quality_status = str(quality_status or "qabul_qilingan").lower()
    if quality_status not in ("qabul_qilingan", "qisman", "rad_etilgan"):
        raise ValueError("Noto'g'ri sifat holati (qabul_qilingan / qisman / rad_etilgan)")

    total_qty = float(order.quantity or 0)
    if total_qty <= 0:
        raise ValueError("Buyurtma miqdori 0 dan katta bo'lishi kerak")

    # Rad etilgan miqdorni aniqlash
    if quality_status == "qabul_qilingan":
        rejected = 0.0
    elif quality_status == "rad_etilgan":
        rejected = total_qty
    else:  # qisman
        try:
            rejected = float(rejected_qty or 0)
        except (TypeError, ValueError):
            raise ValueError("Qisman qabul uchun rad etilgan miqdor son bo'lishi kerak")
        if rejected <= 0 or rejected >= total_qty:
            raise ValueError(
                f"Qisman qabulda rad etilgan miqdor 0 va {total_qty:,.0f} oralig'ida bo'lishi kerak"
            )

    accepted = round(total_qty - rejected, 2)
    rejected = round(rejected, 2)

    # Akt raqami: SQC-YYYYMM-NNNN
    now = datetime.now()
    act_count = db.query(models.ProductionQC).filter(
        extract("year", models.ProductionQC.created_at) == now.year,
        extract("month", models.ProductionQC.created_at) == now.month,
    ).count() + 1
    act_number = f"SQC-{now.strftime('%Y%m')}-{act_count:04d}"

    product = db.query(models.Product).filter(
        models.Product.id == order.product_id
    ).first()
    target_wh = (product.warehouse or "tayyor") if product else "tayyor"

    # Ombordagi harakat yozuvlari:
    # 1) To'liq chiqim tayyor omborga kirim sifatida (+quantity)
    db.add(models.WarehouseTransaction(
        product_id=order.product_id,
        quantity=total_qty,
        transaction_type=models.TransactionType.PRODUCTION,
        user_id=user_id,
        user_name=created_by or "Tizim",
        document_number=act_number,
        target_warehouse=target_wh,
        notes=f"Sifat nazorati {act_number}: qabul ({accepted:,.2f})",
    ))
    # 2) Rad etilgan qism brak omboriga chiqim sifatida (-rejected)
    if rejected > 0:
        db.add(models.WarehouseTransaction(
            product_id=order.product_id,
            quantity=-rejected,
            transaction_type=models.TransactionType.PRODUCTION,
            user_id=user_id,
            user_name=created_by or "Tizim",
            document_number=act_number,
            target_warehouse="brak",
            notes=f"Sifat nazorati {act_number}: brak ({rejected:,.2f})",
        ))

    qc = models.ProductionQC(
        act_number=act_number,
        order_id=order.id,
        product_id=order.product_id,
        quantity_checked=total_qty,
        accepted_qty=accepted,
        rejected_qty=rejected,
        quality_status=quality_status,
        photo_path=photo_path,
        notes=notes,
        created_by=created_by,
    )
    db.add(qc)

    # Buyurtma holatini yangilash
    order.qc_status = quality_status
    order.qc_at = datetime.utcnow()
    order.accepted_qty = accepted
    order.rejected_qty = rejected

    try:
        create_system_log(
            db, user_id=user_id, user_name=created_by,
            action=f"Sifat nazorati: {act_number} {accepted:,.0f} qabul / {rejected:,.0f} brak ({quality_status})",
            module="production",
        )
    except Exception:
        pass

    db.commit()
    db.refresh(qc)
    return qc


def get_production_qc(db: Session, qc_id: int) -> Optional[models.ProductionQC]:
    """QC aktini ID bo'yicha olish"""
    return db.query(models.ProductionQC).filter(
        models.ProductionQC.id == qc_id
    ).first()


def list_production_qc_acts(db: Session, limit: int = 50) -> List[models.ProductionQC]:
    """Sifat nazorati aktlari ro'yxati (eng yangilari avval)"""
    return db.query(models.ProductionQC).order_by(
        models.ProductionQC.created_at.desc()
    ).limit(limit).all()


def production_qc_to_dict(db: Session, qc: models.ProductionQC) -> Dict:
    """QC aktini API/bot uchun dict ko'rinishiga o'tkazish"""
    order = db.query(models.ProductionOrder).filter(
        models.ProductionOrder.id == qc.order_id
    ).first() if qc.order_id else None
    product = db.query(models.Product).filter(
        models.Product.id == qc.product_id
    ).first() if qc.product_id else None
    return {
        "id": qc.id,
        "act_number": qc.act_number,
        "order_id": qc.order_id,
        "order_number": order.order_number if order else None,
        "product_id": qc.product_id,
        "product_name": product.name if product else None,
        "unit": product.unit if product else None,
        "quantity_checked": qc.quantity_checked,
        "accepted_qty": qc.accepted_qty or 0,
        "rejected_qty": qc.rejected_qty or 0,
        "quality_status": qc.quality_status,
        "quality_status_label": QC_STATUS_LABELS.get(qc.quality_status, qc.quality_status),
        "photo_path": qc.photo_path,
        "notes": qc.notes,
        "created_by": qc.created_by,
        "created_at": qc.created_at.isoformat() if qc.created_at else None,
    }


# =============== YOQILG'I NAZORATI (TZ: D-bo'lim) ===============
def create_fuel_log(db: Session, data: Dict) -> models.FuelLog:
    """Yoqilg'i quyishni qayd etish. Avtomatik prev_odometer va xarajat hisoblanadi."""
    prev = db.query(models.FuelLog).filter(
        models.FuelLog.driver_id == data.get("driver_id")
    ).order_by(models.FuelLog.created_at.desc()).first() if data.get("driver_id") else None
    data["prev_odometer_km"] = prev.odometer_km if prev else None
    if data.get("odometer_km") and not data.get("total_cost") and data.get("liters"):
        data["total_cost"] = (data.get("price_per_liter") or 0) * data["liters"]
    entry = models.FuelLog(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_fuel_logs(db: Session, limit: int = 100) -> List[models.FuelLog]:
    return db.query(models.FuelLog).order_by(
        models.FuelLog.created_at.desc()).limit(limit).all()


def get_fuel_efficiency(db: Session, driver_id: int = None, norm_liters_per_100km: float = 15.0,
                        days: int = 30) -> Dict:
    """Haydovchi bo'yicha 100 km ga sarflangan yoqilg'i. Me'yordan oshsa ogohlantiradi."""
    q = db.query(models.FuelLog)
    if driver_id:
        q = q.filter(models.FuelLog.driver_id == driver_id)
    since = datetime.utcnow() - timedelta(days=days)
    q = q.filter(models.FuelLog.created_at >= since).order_by(models.FuelLog.created_at.asc())
    logs = q.all()
    # Odometer bo'yicha aniqlik: oxirgi - birinchi ko'rsatkichlar farqi
    total_liters = sum(l.liters or 0 for l in logs)
    total_cost = sum(l.total_cost or 0 for l in logs)
    distances = []
    for i in range(1, len(logs)):
        if logs[i].odometer_km and logs[i - 1].odometer_km and logs[i].odometer_km > logs[i - 1].odometer_km:
            distances.append((logs[i].odometer_km - logs[i - 1].odometer_km, logs[i].liters or 0))
    total_km = sum(d for d, _ in distances)
    liters_used_for_km = sum(l for _, l in distances)
    avg_liters_100 = (liters_used_for_km / total_km * 100) if total_km > 0 else None
    return {
        "driver_id": driver_id,
        "logs_count": len(logs),
        "total_liters": round(total_liters, 2),
        "total_cost": round(total_cost, 0),
        "total_km": round(total_km, 1),
        "avg_liters_per_100km": round(avg_liters_100, 2) if avg_liters_100 is not None else None,
        "norm_liters_per_100km": norm_liters_per_100km,
        "over_norm": bool(avg_liters_100 and avg_liters_100 > norm_liters_per_100km),
        "over_norm_pct": round((avg_liters_100 / norm_liters_per_100km - 1) * 100, 1) if avg_liters_100 and norm_liters_per_100km else 0,
    }


# =============== AVANS HISOBOti / XARAJAT (TZ: Avans) ===============
def create_expense_report(db: Session, data: Dict) -> models.ExpenseReport:
    if not data.get("report_number"):
        prefix = "EXP-%s-" % datetime.utcnow().strftime("%Y%m")
        count = db.query(models.ExpenseReport).filter(
            models.ExpenseReport.report_number.like(prefix + "%")).count() + 1
        data["report_number"] = "%s%04d" % (prefix, count)
    data["status"] = "kutilmoqda"
    report = models.ExpenseReport(**data)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_expense_reports(db: Session, status: str = None, limit: int = 100) -> List[models.ExpenseReport]:
    q = db.query(models.ExpenseReport)
    if status:
        q = q.filter(models.ExpenseReport.status == status)
    return q.order_by(models.ExpenseReport.created_at.desc()).limit(limit).all()


def review_expense_report(db: Session, report_id: int, status: str, reviewed_by: str = None,
                          note: str = None) -> Optional[models.ExpenseReport]:
    """Direktor avans hisobotini tasdiqlaydi / rad etadi."""
    report = db.query(models.ExpenseReport).filter(
        models.ExpenseReport.id == report_id).first()
    if not report:
        return None
    report.status = status
    report.reviewed_by = reviewed_by
    report.reviewed_at = datetime.utcnow()
    report.note = note
    db.commit()
    db.refresh(report)
    return report


def get_expense_totals(db: Session, days: int = 30) -> Dict:
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        models.ExpenseReport.status,
        func.coalesce(func.sum(models.ExpenseReport.amount), 0)
    ).filter(models.ExpenseReport.created_at >= since).group_by(
        models.ExpenseReport.status).all()
    total = db.query(func.coalesce(func.sum(models.ExpenseReport.amount), 0)).filter(
        models.ExpenseReport.created_at >= since,
        models.ExpenseReport.status == "tasdiqlangan").scalar()
    by_status = {s: round(float(a), 0) for s, a in rows}
    return {
        "days": days,
        "approved_total": round(float(total or 0), 0),
        "by_status": by_status,
        "count": sum(a for _, a in rows),
    }


# =============== YIG'ISH VARAQASI (Picking list, TZ: 4-modul) ===============
def create_picking_list(db: Session, data: Dict) -> models.PickingList:
    if not data.get("picking_number"):
        prefix = "PKG-%s-" % datetime.utcnow().strftime("%Y%m%d")
        count = db.query(models.PickingList).filter(
            models.PickingList.picking_number.like(prefix + "%")).count() + 1
        data["picking_number"] = "%s%03d" % (prefix, count)
    item = models.PickingList(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_picking_lists(db: Session, status: str = None, limit: int = 100) -> List[models.PickingList]:
    q = db.query(models.PickingList)
    if status:
        q = q.filter(models.PickingList.status == status)
    return q.order_by(models.PickingList.created_at.desc()).limit(limit).all()


def update_picking_status(db: Session, picking_id: int, status: str,
                          picked_by: str = None) -> Optional[models.PickingList]:
    item = db.query(models.PickingList).filter(models.PickingList.id == picking_id).first()
    if not item:
        return None
    item.status = status
    if picked_by:
        item.picked_by = picked_by
    if status in ("tayyor", "yuborilgan") and not item.picked_at:
        item.picked_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


# =============== SHUBHALI HARAKAT DETEKTORI (TZ: Xavfsizlik) ===============
def log_suspicious_activity(db: Session, activity_type: str, description: str = None,
                            severity: str = "medium", user_name: str = None,
                            user_id: int = None, entity_id: int = None) -> models.SuspiciousActivity:
    act = models.SuspiciousActivity(
        activity_type=activity_type, description=description, severity=severity,
        user_name=user_name, user_id=user_id, entity_id=entity_id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def list_suspicious_activities(db: Session, status: str = None, limit: int = 100) -> List[models.SuspiciousActivity]:
    q = db.query(models.SuspiciousActivity)
    if status:
        q = q.filter(models.SuspiciousActivity.status == status)
    return q.order_by(models.SuspiciousActivity.created_at.desc()).limit(limit).all()


def update_suspicious_status(db: Session, act_id: int, status: str) -> Optional[models.SuspiciousActivity]:
    act = db.query(models.SuspiciousActivity).filter(models.SuspiciousActivity.id == act_id).first()
    if not act:
        return None
    act.status = status
    db.commit()
    db.refresh(act)
    return act


# =============== SOTUVCHILAR REYTINGI (TZ: "Sotuvchi reytingi") ===============
def get_seller_ratings(db: Session, days: int = 30, limit: int = 20) -> List[Dict]:
    """Har bir sotuvchi uchun: savdo summa, cheklar soni, o'rtacha chek va reyting."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        models.Sale.user_name,
        func.count(models.Sale.id).label("sales_count"),
        func.sum(models.Sale.total_amount).label("total_sales"),
        func.avg(models.Sale.total_amount).label("avg_check"),
    ).filter(
        models.Sale.created_at >= since,
        models.Sale.user_name.isnot(None),
        models.Sale.user_name != "",
    ).group_by(models.Sale.user_name).all()

    result = []
    for r in rows:
        total = float(r.total_sales or 0)
        count = int(r.sales_count or 0)
        result.append({
            "seller": r.user_name,
            "sales_count": count,
            "total_sales": round(total, 0),
            "avg_check": round(float(r.avg_check or 0), 0),
            "score": round(total * 0.7 + (r.avg_check or 0) * 0.3, 0) if r.avg_check else round(total * 0.7, 0),
        })
    result.sort(key=lambda x: x["score"], reverse=True)
    # O'rinlar
    for i, r in enumerate(result, start=1):
        r["rank"] = i
    return result[:limit]
