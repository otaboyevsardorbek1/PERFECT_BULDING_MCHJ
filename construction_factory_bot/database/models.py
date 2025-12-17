from sqlalchemy import (
    create_engine, Column, Integer, String, Float, 
    DateTime, Boolean, ForeignKey, Text, Enum, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime, time
import enum

from config import DATABASE_URL

# Database engine yaratish
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enum turlari
class TransactionType(enum.Enum):
    INCOME = "kirim"
    OUTCOME = "chiqim"
    PRODUCTION = "ishlab_chiqarish"
    SALE = "sotish"
    RETURN = "qaytarish"

class OrderStatus(enum.Enum):
    PENDING = "kutilmoqda"
    IN_PROGRESS = "jarayonda"
    COMPLETED = "tayyor"
    CANCELLED = "bekor_qilingan"
    DELIVERED = "yetkazib_berildi"

class EmployeeStatus(enum.Enum):
    ACTIVE = "faol"
    ON_LEAVE = "ta'tilda"
    FIRED = "ishdan_bo'shatilgan"
    VACATION = "dam_olish"

class NotificationStatus(enum.Enum):
    PENDING = "kutilmoqda"
    SENT = "yuborilgan"
    READ = "o'qilgan"
    FAILED = "xatolik"

# Jadval modellari
class RawMaterial(Base):
    """Xom ashyolar jadvali"""
    __tablename__ = "raw_materials"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    category = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=False)
    current_stock = Column(Float, default=0.0)
    min_stock = Column(Float, default=0.0)
    max_stock = Column(Float, default=10000.0)
    price_per_unit = Column(Float, default=0.0)
    supplier = Column(String(100), nullable=True)
    last_purchase_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    formula_items = relationship("ProductFormula", back_populates="raw_material")
    transactions = relationship("WarehouseTransaction", back_populates="raw_material")

class Product(Base):
    """Mahsulotlar jadvali"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    category = Column(String(50), nullable=False)
    unit = Column(String(20), nullable=False)
    selling_price = Column(Float, default=0.0)
    production_cost = Column(Float, default=0.0)
    profit_margin = Column(Float, default=0.4)  # 40% foyda
    barcode = Column(String(50), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    formula_items = relationship("ProductFormula", back_populates="product")
    transactions = relationship("WarehouseTransaction", back_populates="product")
    orders = relationship("ProductionOrder", back_populates="product")
    sales = relationship("Sale", back_populates="product")

class ProductFormula(Base):
    """Mahsulot formulalari jadvali"""
    __tablename__ = "product_formulas"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    waste_percentage = Column(Float, default=0.05)  # 5% chiqindi
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="formula_items")
    raw_material = relationship("RawMaterial", back_populates="formula_items")
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class WarehouseTransaction(Base):
    """Ombordagi harakatlar jadvali"""
    __tablename__ = "warehouse_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=True)
    quantity = Column(Float, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    user_id = Column(Integer, nullable=False)
    user_name = Column(String(100), nullable=True)
    document_number = Column(String(50), nullable=True)
    counterparty = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="transactions")
    raw_material = relationship("RawMaterial", back_populates="transactions")

class ProductionOrder(Base):
    """Ishlab chiqarish buyurtmalari jadvali"""
    __tablename__ = "production_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    priority = Column(Integer, default=1)  # 1-eng past, 5-eng yuqori
    planned_start = Column(DateTime, nullable=True)
    planned_end = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    total_cost = Column(Float, default=0.0)
    total_revenue = Column(Float, default=0.0)
    profit = Column(Float, default=0.0)
    responsible_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="orders")
    responsible = relationship("Employee", back_populates="orders")

class Employee(Base):
    """Xodimlar jadvali"""
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=True)
    full_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False)
    position = Column(String(50), nullable=False)
    department = Column(String(50), nullable=False)
    status = Column(Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE)
    hire_date = Column(DateTime, nullable=False)
    salary = Column(Float, default=0.0)
    hourly_rate = Column(Float, default=0.0)
    bank_account = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    passport_data = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    orders = relationship("ProductionOrder", back_populates="responsible")
    work_hours = relationship("WorkHours", back_populates="employee")
    salaries = relationship("SalaryPayment", back_populates="employee")

class WorkHours(Base):
    """Ish vaqtlari jadvali"""
    __tablename__ = "work_hours"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    hours_worked = Column(Float, default=0.0)
    overtime_hours = Column(Float, default=0.0)
    shift_type = Column(String(20), default="day")  # day, night, evening
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    employee = relationship("Employee", back_populates="work_hours")

class SalaryPayment(Base):
    """Maosh to'lovlari jadvali"""
    __tablename__ = "salary_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    base_salary = Column(Float, default=0.0)
    bonus = Column(Float, default=0.0)
    overtime_pay = Column(Float, default=0.0)
    deduction = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    payment_date = Column(DateTime, nullable=True)
    payment_method = Column(String(20), default="cash")  # cash, bank, card
    status = Column(String(20), default="pending")  # pending, paid, cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    employee = relationship("Employee", back_populates="salaries")

class Sale(Base):
    """Sotuvlar jadvali"""
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=True)
    payment_method = Column(String(20), default="cash")
    status = Column(String(20), default="completed")
    sale_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="sales")

class Notification(Base):
    """Bildirishnomalar jadvali"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    recipient_id = Column(Integer, nullable=True)  # Employee ID yoki 0=hamma
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    priority = Column(Integer, default=1)  # 1-5
    scheduled_time = Column(DateTime, nullable=True)
    sent_time = Column(DateTime, nullable=True)
    read_time = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)  # Qo'shimcha ma'lumotlar
    created_at = Column(DateTime, default=datetime.utcnow)
    
class SystemLog(Base):
    """Tizim loglari jadvali"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    user_name = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False)
    module = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

# Jadvalarni yaratish
def create_tables():
    """Database jadvallarini yaratish"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")

if __name__ == "__main__":
    create_tables()