from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, extract
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
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