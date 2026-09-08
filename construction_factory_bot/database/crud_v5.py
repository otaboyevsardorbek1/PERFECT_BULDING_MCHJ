"""
CRUD v5 — spec (construction_factory_bot.md) REST API ro'yxati uchun qo'shimcha
funksiyalar: narx tarixi, omborlar, xodimlar (users), ishlab chiqarish,
to'lovlar, ombor harakatlari tarixi va hisobotlar.

Mavjud `database/crud.py` bilan bir xil uslubda ishlaydi.
"""
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from . import models


# =============== NARX TARIXI (TZ: "Sana bo'yicha narx tarixi") ===============
def record_price_change(db: Session, product: models.Product, new_price: float,
                        price_type: str = "selling", reason: str = None,
                        changed_by: str = None) -> models.ProductPriceHistory:
    """Narx o'zgarishini tarixga yozadi (eski narx saqlanib qoladi)."""
    old_price = None
    if price_type == "wholesale":
        old_price = product.wholesale_price
        product.wholesale_price = new_price
    elif price_type == "retail":
        old_price = product.retail_price
        product.retail_price = new_price
    elif price_type == "cost":
        old_price = product.production_cost
        product.production_cost = new_price
    else:
        old_price = product.selling_price
        product.selling_price = new_price
    entry = models.ProductPriceHistory(
        product_id=product.id,
        product_name=product.name,
        old_price=old_price,
        new_price=new_price,
        price_type=price_type,
        reason=reason,
        changed_by=changed_by,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_price_history(db: Session, product_id: int = None,
                       price_type: str = None, limit: int = 100) -> List[Dict]:
    """Narx tarixi ro'yxati (filtr: mahsulot, narx turi)."""
    q = db.query(models.ProductPriceHistory)
    if product_id:
        q = q.filter(models.ProductPriceHistory.product_id == product_id)
    if price_type:
        q = q.filter(models.ProductPriceHistory.price_type == price_type)
    rows = q.order_by(desc(models.ProductPriceHistory.changed_at)).limit(limit).all()
    return [{
        "id": r.id,
        "product_id": r.product_id,
        "product_name": r.product_name,
        "old_price": r.old_price,
        "new_price": r.new_price,
        "price_type": r.price_type,
        "reason": r.reason,
        "changed_by": r.changed_by,
        "changed_at": r.changed_at.isoformat() if r.changed_at else None,
    } for r in rows]


# =============== OMBORLAR (TZ: Warehouses CRUD) ===============
def create_warehouse(db: Session, data: Dict) -> models.Warehouse:
    wh = models.Warehouse(**{k: v for k, v in data.items() if hasattr(models.Warehouse, k)})
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return wh


def get_warehouse(db: Session, warehouse_id: int) -> Optional[models.Warehouse]:
    return db.query(models.Warehouse).filter(models.Warehouse.id == warehouse_id).first()


def list_warehouses(db: Session, active_only: bool = True) -> List[models.Warehouse]:
    q = db.query(models.Warehouse)
    if active_only:
        q = q.filter(models.Warehouse.is_active.is_(True))
    return q.order_by(models.Warehouse.name).all()


def update_warehouse(db: Session, warehouse_id: int, data: Dict) -> Optional[models.Warehouse]:
    wh = get_warehouse(db, warehouse_id)
    if not wh:
        return None
    for k, v in data.items():
        if hasattr(wh, k):
            setattr(wh, k, v)
    db.commit()
    db.refresh(wh)
    return wh


def warehouse_to_dict(wh: models.Warehouse) -> Dict:
    return {
        "id": wh.id,
        "name": wh.name,
        "warehouse_type": wh.warehouse_type,
        "address": wh.address,
        "manager_name": wh.manager_name,
        "sectors": wh.sectors,
        "is_active": bool(wh.is_active),
        "notes": wh.notes,
        "created_at": wh.created_at.isoformat() if wh.created_at else None,
    }


# =============== KATEGORIYALAR ===============
def list_categories(db: Session, item_type: str = "product") -> List[Dict]:
    """Mavjud kategoriyalar ro'yxati (products yoki raw_materials)."""
    model_cls = models.RawMaterial if item_type == "raw" else models.Product
    rows = db.query(model_cls.category).filter(
        model_cls.category.isnot(None), model_cls.category != ""
    ).distinct().order_by(model_cls.category).all()
    return [{"name": r[0]} for r in rows]


# =============== XODIMLAR (TZ: Users API) ===============
def parse_employee_status(value: str) -> models.EmployeeStatus:
    """Status matnini EmployeeStatus enum'iga moslashtiradi."""
    mapping = {
        "faol": models.EmployeeStatus.ACTIVE,
        "ta'tilda": models.EmployeeStatus.ON_LEAVE,
        "dam_olish": models.EmployeeStatus.VACATION,
        "ishdan_ketgan": models.EmployeeStatus.FIRED,
        "ishdan_bo'shatilgan": models.EmployeeStatus.FIRED,
        "bloklangan": models.EmployeeStatus.FIRED,
    }
    return mapping.get(str(value).strip(), models.EmployeeStatus.ACTIVE)


def list_employees(db: Session, status: str = None) -> List[models.Employee]:
    q = db.query(models.Employee)
    if status:
        q = q.filter(models.Employee.status == parse_employee_status(status))
    return q.order_by(models.Employee.full_name).all()


def get_employee(db: Session, employee_id: int) -> Optional[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.id == employee_id).first()


def update_employee(db: Session, employee_id: int, data: Dict) -> Optional[models.Employee]:
    emp = get_employee(db, employee_id)
    if not emp:
        return None
    for k, v in data.items():
        if hasattr(emp, k) and k not in ("id", "telegram_id", "otp_secret", "otp_enabled", "password_hash"):
            setattr(emp, k, v)
    db.commit()
    db.refresh(emp)
    return emp


def delete_employee(db: Session, employee_id: int) -> bool:
    emp = get_employee(db, employee_id)
    if not emp:
        return False
    db.delete(emp)
    db.commit()
    return True


def set_employee_status(db: Session, employee_id: int, status: str) -> Optional[models.Employee]:
    emp = get_employee(db, employee_id)
    if not emp:
        return None
    emp.status = parse_employee_status(status)
    db.commit()
    db.refresh(emp)
    return emp


def employee_to_dict(emp: models.Employee) -> Dict:
    return {
        "id": emp.id,
        "telegram_id": emp.telegram_id,
        "full_name": emp.full_name,
        "phone_number": emp.phone_number,
        "position": emp.position,
        "department": emp.department,
        "status": emp.status.value if hasattr(emp.status, "value") else str(emp.status),
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
        "salary": emp.salary,
        "hourly_rate": emp.hourly_rate,
        "bank_account": emp.bank_account,
        "address": emp.address,
        "is_admin": bool(emp.is_admin),
        "role": emp.role,
        "has_password": bool(emp.password_hash),
        "two_fa_enabled": bool(emp.otp_enabled),
        "created_at": emp.created_at.isoformat() if emp.created_at else None,
    }


# =============== ISHLAB CHIQARISH BUYURTMALARI (API) ===============
def parse_order_status(value: str) -> models.OrderStatus:
    """Status matnini OrderStatus enum'iga moslashtiradi."""
    mapping = {
        "kutilmoqda": models.OrderStatus.PENDING,
        "jarayonda": models.OrderStatus.IN_PROGRESS,
        "tayyor": models.OrderStatus.COMPLETED,
        "bekor": models.OrderStatus.CANCELLED,
        "bekor_qilingan": models.OrderStatus.CANCELLED,
        "yetkazib_berildi": models.OrderStatus.DELIVERED,
    }
    return mapping.get(str(value).strip(), models.OrderStatus.PENDING)


def list_production_orders(db: Session, status: str = None, limit: int = 100) -> List[models.ProductionOrder]:
    q = db.query(models.ProductionOrder)
    if status:
        q = q.filter(models.ProductionOrder.status == parse_order_status(status))
    return q.order_by(desc(models.ProductionOrder.created_at)).limit(limit).all()


def update_production_order_status(db: Session, order_id: int, status: str,
                                   actual_start: datetime = None,
                                   actual_end: datetime = None) -> Optional[models.ProductionOrder]:
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        return None
    order.status = parse_order_status(status)
    if actual_start:
        order.actual_start = actual_start
    if actual_end:
        order.actual_end = actual_end
    db.commit()
    db.refresh(order)
    return order


def production_order_to_dict(db: Session, order: models.ProductionOrder) -> Dict:
    product = db.query(models.Product).filter(models.Product.id == order.product_id).first()
    return {
        "id": order.id,
        "order_number": order.order_number,
        "product_id": order.product_id,
        "product_name": product.name if product else None,
        "quantity": order.quantity,
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
        "priority": order.priority,
        "planned_start": order.planned_start.isoformat() if order.planned_start else None,
        "planned_end": order.planned_end.isoformat() if order.planned_end else None,
        "actual_start": order.actual_start.isoformat() if order.actual_start else None,
        "actual_end": order.actual_end.isoformat() if order.actual_end else None,
        "total_cost": order.total_cost,
        "total_revenue": order.total_revenue,
        "profit": order.profit,
        "qc_status": order.qc_status,
        "accepted_qty": order.accepted_qty,
        "rejected_qty": order.rejected_qty,
        "notes": order.notes,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


# =============== TO'LOVLAR (TZ: Payments API) ===============
def list_payments(db: Session, start_date: datetime = None, end_date: datetime = None,
                  limit: int = 100) -> List[models.Payment]:
    q = db.query(models.Payment)
    if start_date:
        q = q.filter(models.Payment.created_at >= start_date)
    if end_date:
        q = q.filter(models.Payment.created_at <= end_date)
    return q.order_by(desc(models.Payment.created_at)).limit(limit).all()


def payment_to_dict(p: models.Payment) -> Dict:
    return {
        "id": p.id,
        "sale_id": p.sale_id,
        "customer_id": p.customer_id,
        "amount": p.amount,
        "method": p.method,
        "payment_type": p.payment_type,
        "payment_date": p.created_at.isoformat() if p.created_at else None,
        "created_by": p.created_by,
        "notes": p.note,
    }


def get_daily_payments(db: Session, day: date = None) -> Dict:
    """Kunlik to'lovlar: naqd/karta/onlayn/nasiya bo'yicha jamlama."""
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    rows = db.query(models.Payment.method, func.sum(models.Payment.amount)).filter(
        models.Payment.created_at >= start,
        models.Payment.created_at <= end,
    ).group_by(models.Payment.method).all()
    result = {"date": day.isoformat(), "total": 0.0, "by_method": {}}
    for method, total in rows:
        result["by_method"][method] = round(float(total or 0), 0)
        result["total"] += float(total or 0)
    result["total"] = round(result["total"], 0)
    return result


# =============== OMBOR HARAKATLARI TARIXI (TZ: Inventory history) ===============
def get_inventory_history(db: Session, item_type: str = None, item_id: int = None,
                          limit: int = 100) -> List[Dict]:
    q = db.query(models.WarehouseTransaction)
    if item_type == "product":
        q = q.filter(models.WarehouseTransaction.product_id.isnot(None))
        if item_id:
            q = q.filter(models.WarehouseTransaction.product_id == item_id)
    elif item_type == "raw":
        q = q.filter(models.WarehouseTransaction.raw_material_id.isnot(None))
        if item_id:
            q = q.filter(models.WarehouseTransaction.raw_material_id == item_id)
    rows = q.order_by(desc(models.WarehouseTransaction.date)).limit(limit).all()
    result = []
    for t in rows:
        name = None
        if t.product_id:
            prod = db.query(models.Product).filter(models.Product.id == t.product_id).first()
            name = prod.name if prod else f"#{t.product_id}"
        elif t.raw_material_id:
            mat = db.query(models.RawMaterial).filter(models.RawMaterial.id == t.raw_material_id).first()
            name = mat.name if mat else f"#{t.raw_material_id}"
        result.append({
            "id": t.id,
            "date": t.date.isoformat() if t.date else None,
            "item": name,
            "item_type": "product" if t.product_id else "raw",
            "quantity": t.quantity,
            "transaction_type": t.transaction_type.value if hasattr(t.transaction_type, "value") else str(t.transaction_type),
            "user_name": t.user_name,
            "document_number": t.document_number,
            "counterparty": t.counterparty,
            "source_warehouse": t.source_warehouse,
            "target_warehouse": t.target_warehouse,
            "notes": t.notes,
        })
    return result


# =============== HISOBOTLAR (TZ: Reports API) ===============
def get_top_customers(db: Session, limit: int = 20, days: int = None) -> List[Dict]:
    q = db.query(
        models.Customer.name,
        models.Customer.phone,
        func.sum(models.Payment.amount).label("total_paid"),
        func.count(models.Sale.id).label("order_count"),
    ).join(models.Sale, models.Sale.customer_id == models.Customer.id).outerjoin(
        models.Payment, models.Payment.sale_id == models.Sale.id
    )
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        q = q.filter(models.Sale.created_at >= since)
    rows = q.group_by(models.Customer.id, models.Customer.name, models.Customer.phone)\
        .order_by(desc(func.sum(models.Payment.amount))).limit(limit).all()
    return [{
        "name": r.name,
        "phone": r.phone,
        "total_paid": round(float(r.total_paid or 0), 0),
        "order_count": int(r.order_count or 0),
    } for r in rows]


def get_sales_by_category(db: Session, days: int = 30) -> List[Dict]:
    """Kategoriya bo'yicha savdo (TZ: Reports — sales-by-category)."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        models.Product.category,
        func.sum(models.Sale.total_amount).label("total"),
        func.sum(models.Sale.quantity).label("qty"),
    ).join(models.Sale, models.Sale.product_id == models.Product.id).filter(
        models.Sale.created_at >= since
    ).group_by(models.Product.category).order_by(desc(func.sum(models.Sale.total_amount))).all()
    return [{
        "category": r.category,
        "total": round(float(r.total or 0), 0),
        "quantity": round(float(r.qty or 0), 1),
    } for r in rows]