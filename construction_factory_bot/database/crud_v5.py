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


# =============== MIJOZ UCHUN MAXSUS NARXLAR (TZ 3.1: "maxsus mijoz narxlari") ===============

def get_customer_prices(db: Session, customer_id: int) -> List[Dict]:
    """Mijozning maxsus narxlari ro'yxati (mahsulot nomi bilan)."""
    rows = db.query(models.CustomerPrice).filter(
        models.CustomerPrice.customer_id == customer_id
    ).all()
    return [{
        "id": cp.id,
        "customer_id": cp.customer_id,
        "product_id": cp.product_id,
        "product_name": cp.product.name if cp.product else None,
        "unit": cp.product.unit if cp.product else None,
        "price": cp.price,
        "created_at": cp.created_at.isoformat() if cp.created_at else None,
    } for cp in rows]


def get_customer_product_price(db: Session, customer_id: int,
                               product_id: int) -> Optional[float]:
    """Mijoz uchun shu mahsulot bo'yicha maxsus narx (bo'lmasa None)."""
    cp = db.query(models.CustomerPrice).filter(
        models.CustomerPrice.customer_id == customer_id,
        models.CustomerPrice.product_id == product_id,
    ).first()
    return cp.price if cp else None


def set_customer_price(db: Session, customer_id: int, product_id: int,
                       price: float) -> Dict:
    """Mijoz maxsus narxini o'rnatish (mavjud bo'lsa yangilaydi)."""
    if price is None or float(price) < 0:
        raise ValueError("price 0 dan katta yoki teng bo'lishi kerak")
    cp = db.query(models.CustomerPrice).filter(
        models.CustomerPrice.customer_id == customer_id,
        models.CustomerPrice.product_id == product_id,
    ).first()
    if cp:
        cp.price = float(price)
    else:
        cp = models.CustomerPrice(
            customer_id=customer_id, product_id=product_id, price=float(price))
        db.add(cp)
    db.commit()
    db.refresh(cp)
    return {
        "id": cp.id, "customer_id": cp.customer_id, "product_id": cp.product_id,
        "product_name": cp.product.name if cp.product else None,
        "price": cp.price,
    }


def delete_customer_price(db: Session, customer_id: int, product_id: int) -> bool:
    """Mijoz maxsus narxini o'chirish."""
    cp = db.query(models.CustomerPrice).filter(
        models.CustomerPrice.customer_id == customer_id,
        models.CustomerPrice.product_id == product_id,
    ).first()
    if not cp:
        return False
    db.delete(cp)
    db.commit()
    return True


def list_products_below_min_stock(db: Session) -> List[Dict]:
    """min_stock chegarasidan past bo'lgan tayyor mahsulotlar (TZ 3.1)."""
    result = []
    for p in db.query(models.Product).filter(models.Product.is_active.is_(True)).all():
        income = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0.0)).filter(
            models.WarehouseTransaction.product_id == p.id,
            models.WarehouseTransaction.transaction_type == models.TransactionType.INCOME,
        ).scalar() or 0.0
        outcome = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0.0)).filter(
            models.WarehouseTransaction.product_id == p.id,
            models.WarehouseTransaction.transaction_type == models.TransactionType.OUTCOME,
        ).scalar() or 0.0
        available = float(income) - float(outcome)
        if float(p.min_stock or 0) > 0 and available < float(p.min_stock):
            result.append({"product": p, "available_qty": available,
                           "min_stock": float(p.min_stock or 0)})
    return result


# =============== v5.3: TRANSPORT VOSITALARI (TZ ERD: vehicles) ===============
def create_vehicle(db: Session, data: Dict) -> models.Vehicle:
    """Yangi transport vositasini yaratish."""
    v = models.Vehicle(
        number=str(data.get("number", "")).strip(),
        brand=str(data.get("brand", "")).strip() or None,
        driver_id=data.get("driver_id"),
        driver_name=str(data.get("driver_name", "")).strip() or None,
        capacity=float(data.get("capacity", 0) or 0),
        fuel_type=str(data.get("fuel_type", "benzin")).strip() or "benzin",
        fuel_norm_per_km=float(data.get("fuel_norm_per_km", 0) or 0),
        status=str(data.get("status", "faol")).strip() or "faol",
        notes=str(data.get("notes", "")).strip() or None,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def get_vehicle(db: Session, vehicle_id: int) -> Optional[models.Vehicle]:
    return db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()


def list_vehicles(db: Session, status: str = None) -> List[models.Vehicle]:
    q = db.query(models.Vehicle)
    if status:
        q = q.filter(models.Vehicle.status == status)
    return q.order_by(models.Vehicle.number).all()


def update_vehicle(db: Session, vehicle_id: int, data: Dict) -> Optional[models.Vehicle]:
    v = get_vehicle(db, vehicle_id)
    if not v:
        return None
    for field in ("number", "brand", "driver_name", "fuel_type", "status", "notes"):
        if field in data and data[field] is not None:
            setattr(v, field, str(data[field]).strip())
    for field in ("driver_id", "capacity", "fuel_norm_per_km"):
        if field in data and data[field] is not None:
            setattr(v, field, float(data[field]))
    db.commit()
    db.refresh(v)
    return v


def delete_vehicle(db: Session, vehicle_id: int) -> bool:
    v = get_vehicle(db, vehicle_id)
    if not v:
        return False
    db.delete(v)
    db.commit()
    return True


def vehicle_to_dict(v: models.Vehicle) -> Dict:
    return {
        "id": v.id,
        "number": v.number,
        "brand": v.brand,
        "driver_id": v.driver_id,
        "driver_name": v.driver_name,
        "capacity": v.capacity,
        "fuel_type": v.fuel_type,
        "fuel_norm_per_km": v.fuel_norm_per_km,
        "status": v.status,
        "notes": v.notes,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


# =============== v5.3: ORTIQCHA ZAXIRA (TZ ERD: max_stock) ===============
def product_available_qty(db: Session, product: models.Product) -> float:
    """Mahsulotning hozirgi erkin qoldig'i (kirim - chiqim)."""
    income = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0.0)).filter(
        models.WarehouseTransaction.product_id == product.id,
        models.WarehouseTransaction.transaction_type == models.TransactionType.INCOME,
    ).scalar() or 0.0
    outcome = db.query(func.coalesce(func.sum(models.WarehouseTransaction.quantity), 0.0)).filter(
        models.WarehouseTransaction.product_id == product.id,
        models.WarehouseTransaction.transaction_type == models.TransactionType.OUTCOME,
    ).scalar() or 0.0
    return float(income) - float(outcome)


def list_products_over_max_stock(db: Session) -> List[Dict]:
    """max_stock chegarasidan yuqori bo'lgan mahsulotlar (ortiqcha zaxira)."""
    result = []
    for p in db.query(models.Product).filter(models.Product.is_active.is_(True)).all():
        available = product_available_qty(db, p)
        if float(p.max_stock or 0) > 0 and available > float(p.max_stock):
            result.append({"product": p, "available_qty": available,
                           "max_stock": float(p.max_stock or 0)})
    return result


def get_warehouse_fill_levels(db: Session) -> List[Dict]:
    """Rangli ombor xaritasi (TZ B-bo'lim): har bir omborning to'liqlik darajasi.

    Qizil = max_stock chegarasidan oshgan, sariq = 70%+, yashil = normal.
    Omborlar: warehouses katalogi + eski string ombor nomlari.
    """
    names = [w.name for w in db.query(models.Warehouse).filter(models.Warehouse.is_active.is_(True)).all()]
    for r in db.query(models.RawMaterial.warehouse).distinct().all():
        if r[0] and r[0] not in names:
            names.append(r[0])
    for r in db.query(models.Product.warehouse).distinct().all():
        if r[0] and r[0] not in names:
            names.append(r[0])
    if "asosiy" not in names:
        names.insert(0, "asosiy")
    result = []
    for name in names:
        items = 0
        capacity = 0.0
        used = 0.0
        # Xom ashyolar
        for rm in db.query(models.RawMaterial).filter(models.RawMaterial.warehouse == name).all():
            items += 1
            cap = float(rm.max_stock or 0)
            if cap > 0:
                capacity += cap
                used += min(float(rm.current_stock or 0), cap)
        # Tayyor mahsulotlar
        for p in db.query(models.Product).filter(models.Product.warehouse == name).all():
            items += 1
            cap = float(p.max_stock or 0)
            if cap > 0:
                capacity += cap
                qty = product_available_qty(db, p)
                used += min(qty, cap)
        fill = round(used / capacity * 100, 1) if capacity > 0 else 0.0
        level = "yashil" if fill < 70 else ("sariq" if fill < 100 else "qizil")
        result.append({"warehouse": name, "items": items, "capacity": round(capacity, 1),
                       "used": round(used, 1), "fill_percent": fill, "level": level})
    return result


# =============== v5.3: AMAL MUDDATI ESLATMASI (TZ 3.1/3.2) ===============
def get_expiring_materials(db: Session, days: int = 30) -> List[Dict]:
    """Amal qilish muddati yaqinlashgan yoki o'tgan xom ashyolar."""
    now = datetime.utcnow()
    horizon = now + timedelta(days=max(days, 1))
    result = []
    for rm in db.query(models.RawMaterial).filter(
        models.RawMaterial.expiry_date.isnot(None)
    ).all():
        expiry = rm.expiry_date
        if expiry.tzinfo:
            expiry_naive = expiry.replace(tzinfo=None)
        else:
            expiry_naive = expiry
        if expiry_naive <= horizon:
            days_left = (expiry_naive - now).days
            result.append({
                "raw_material_id": rm.id,
                "name": rm.name,
                "batch_number": rm.batch_number,
                "certificate_number": rm.certificate_number,
                "expiry_date": expiry.isoformat() if expiry else None,
                "days_left": days_left,
                "status": "muddati_o'tgan" if days_left < 0 else "yaqinlashmoqda",
                "current_stock": float(rm.current_stock or 0),
                "supplier": rm.supplier,
            })
    result.sort(key=lambda x: x["days_left"])
    return result


# =============== v5.3: XODIM SMENASI KALENDARI (TZ E-bo'lim) ===============
def get_work_schedule(db: Session, month: str = None) -> Dict:
    """Bir oy uchun xodimlar smenasi kalendari.

    month: 'YYYY-MM' (standart — joriy oy). Har bir xodim uchun ishlagan
    kunlar soni, jami soatlar, qo'shimcha vaqt va holati (ta'tilda / faol).
    """
    try:
        if month and len(month) == 7:
            year = int(month[:4])
            mon = int(month[5:7])
        else:
            now = datetime.utcnow()
            year, mon = now.year, now.month
        start = datetime(year, mon, 1)
        if mon == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, mon + 1, 1)
    except (ValueError, TypeError):
        now = datetime.utcnow()
        start = datetime(now.year, now.month, 1)
        end = datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)

    rows = []
    for emp in db.query(models.Employee).order_by(models.Employee.full_name).all():
        wh = db.query(models.WorkHours).filter(
            models.WorkHours.employee_id == emp.id,
            models.WorkHours.start_time >= start,
            models.WorkHours.start_time < end,
        ).all()
        total_hours = sum(float(w.hours_worked or 0) for w in wh)
        overtime = sum(float(w.overtime_hours or 0) for w in wh)
        work_days = {w.start_time.date() for w in wh if w.start_time}
        rows.append({
            "employee_id": emp.id,
            "full_name": emp.full_name,
            "role": emp.role or emp.position or "-",
            "status": emp.status.value if hasattr(emp.status, "value") else str(emp.status or "faol"),
            "work_days": len(work_days),
            "total_hours": round(total_hours, 2),
            "overtime_hours": round(overtime, 2),
            "shifts": [
                {"date": w.start_time.date().isoformat(), "shift_type": w.shift_type,
                 "hours": round(float(w.hours_worked or 0), 2)}
                for w in sorted(wh, key=lambda x: x.start_time)
            ][-31:],
        })
    return {"month": start.strftime("%Y-%m"), "employees": rows}


# =============== v5.3: XODIM OCHIQ OPERATSIYALARI (TZ H-bo'lim) ===============
def get_employee_open_operations(db: Session, employee_id: int) -> Dict:
    """Xodim ishdan ketmoqchi bo'lsa — ochiq operatsiyalari ro'yxati.

    Direktor topshiriq sifatida ko'radi: tugallanmagan sotuvlar (nasiya),
    faol yetkazib berishlar, ochiq yig'ish varaqalari, jarayondagi ishlab
    chiqarish buyurtmalari va ochiq kassa smenasi.
    """
    emp = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not emp:
        return None
    emp_name = emp.full_name or emp.username or "-"
    # Nasiya sotuvlari (to'liq to'lanmagan)
    open_sales = db.query(models.Sale).filter(
        models.Sale.is_credit.is_(True),
        models.Sale.credit_status.in_(("qisman", "tolanmagan", "muddati_otgan")),
    ).all()
    sales_list = [
        {"id": s.id, "customer_name": s.customer_name,
         "total": float(s.total_amount or 0), "paid": float(s.paid_amount or 0),
         "remaining": round(float(s.total_amount or 0) - float(s.paid_amount or 0), 2)}
        for s in open_sales
    ]
    # Faol yetkazib berishlar
    deliveries = db.query(models.Delivery).filter(
        models.Delivery.status.in_(("tayinlangan", "yo'lda"))
    ).all()
    delivery_list = [
        {"id": d.id, "delivery_number": d.delivery_number, "status": d.status,
         "customer_name": d.customer_name, "product_name": d.product_name}
        for d in deliveries
    ]
    # Ochiq yig'ish varaqalari
    picking = db.query(models.PickingList).filter(
        models.PickingList.status.in_(("yangi", "jarayonda"))
    ).all()
    picking_list = [
        {"id": p.id, "picking_number": p.picking_number, "product_name": p.product_name,
         "quantity": float(p.quantity or 0), "status": p.status}
        for p in picking
    ]
    # Jarayondagi ishlab chiqarish buyurtmalari
    production = db.query(models.ProductionOrder).filter(
        models.ProductionOrder.status.in_(("yangi", "jarayonda", "ishlab_chiqarilmoqda"))
    ).all()
    production_list = [
        {"id": o.id, "product_name": o.product_name, "quantity": float(o.quantity or 0),
         "status": o.status, "start_date": o.start_date.isoformat() if o.start_date else None}
        for o in production
    ]
    # Ochiq kassa smenasi
    open_shift = db.query(models.CashShift).filter(models.CashShift.status == "ochiq").first()
    return {
        "employee_id": emp.id,
        "full_name": emp_name,
        "open_sales": sales_list,
        "active_deliveries": delivery_list,
        "open_picking_lists": picking_list,
        "in_progress_production": production_list,
        "open_cash_shift": {"id": open_shift.id, "cashier_name": open_shift.cashier_name}
        if open_shift else None,
        "total_open_items": len(sales_list) + len(delivery_list) + len(picking_list)
        + len(production_list) + (1 if open_shift else 0),
    }


# =============== v5.3: "NIMA BO'LSA?" TAHLILI (TZ E-bo'lim) ===============
def what_if_analysis(db: Session, scenario: str = "price_down", percent: float = 5.0,
                     product_id: int = None, days: int = 90) -> Dict:
    """"Nima bo'lsa?" tahlili — tarixiy sotuvlar asosida prognoz.

    scenario: price_down (narx pasayishi), price_up (narx oshishi),
              discount (chegirma foizi). Tizim o'tgan davrdagi sotuvlar,
              o'rtacha chek va qoldiq asosida taxminiy ta'sirni hisoblaydi.
    """
    now = datetime.utcnow()
    start = now - timedelta(days=max(days, 7))
    pct = float(percent or 0)

    def _base():
        q = db.query(models.Sale).filter(models.Sale.sale_date >= start)
        if product_id:
            q = q.filter(models.Sale.product_id == product_id)
        sales = q.all()
        revenue = sum(float(s.total_amount or 0) for s in sales)
        qty = sum(float(s.quantity or 0) for s in sales)
        count = len(sales)
        avg_check = revenue / count if count else 0.0
        return revenue, qty, count, avg_check

    revenue, qty, count, avg_check = _base()
    if scenario == "price_down":
        # Narx p% pasaysa: talab ~ p*0.6% oshadi (konservativ elastiklik)
        demand_boost = pct * 0.6
        new_revenue = revenue * (1 - pct / 100) * (1 + demand_boost / 100)
        scenario_label = f"Narx {pct}% pasaytirilsa"
    elif scenario == "price_up":
        demand_drop = pct * 0.5
        new_revenue = revenue * (1 + pct / 100) * (1 - demand_drop / 100)
        scenario_label = f"Narx {pct}% oshirilsa"
    elif scenario == "discount":
        new_revenue = revenue * (1 - pct / 100)
        scenario_label = f"Chegirma {pct}% berilsa (marja kamayadi)"
    else:
        new_revenue = revenue
        scenario_label = scenario

    return {
        "scenario": scenario,
        "scenario_label": scenario_label,
        "percent": pct,
        "period_days": days,
        "base_revenue": round(revenue, 2),
        "base_quantity": round(qty, 2),
        "base_order_count": count,
        "avg_check": round(avg_check, 2),
        "projected_revenue": round(new_revenue, 2),
        "delta": round(new_revenue - revenue, 2),
        "delta_percent": round((new_revenue - revenue) / revenue * 100, 2) if revenue else 0.0,
        "note": "Konservativ talab elastikligi asosida taxminiy hisob (o'tgan {} kun ma'lumotlari)".format(days),
    }