from sqlalchemy import (
    create_engine, Column, Integer, String, Float, 
    DateTime, Boolean, ForeignKey, Text, Enum, JSON, inspect, text, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime, time
import enum
import logging

from config import DATABASE_URL

logger = logging.getLogger(__name__)

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
    TRANSFER = "kochirish"
    RESERVATION = "rezervatsiya"
    INVENTORY = "inventarizatsiya"

class ReservationStatus(enum.Enum):
    ACTIVE = "faol"
    COMPLETED = "yakunlangan"
    CANCELLED = "bekor_qilingan"
    RELEASED = "yechilgan"  # muddati tugab avtomatik bo'shatilgan

class QualityStatus(enum.Enum):
    ACCEPTED = "qabul_qilingan"
    REJECTED = "rad_etilgan"
    PARTIAL = "qisman"

class CustomerStatus(enum.Enum):
    ACTIVE = "faol"
    BLOCKED = "bloklangan"
    VIP = "vip"

class CreditStatus(enum.Enum):
    PAID = "toliq_tolangan"
    PARTIAL = "qisman"
    UNPAID = "tolanmagan"
    OVERDUE = "muddati_otgan"

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
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)  # Boglangan yetkazib beruvchi
    warehouse = Column(String(50), default="asosiy")  # asosiy, xomashyo, tayyor, brak
    sector = Column(String(20), nullable=True)  # A1, B2, C3 sektor
    storage_conditions = Column(String(100), nullable=True)  # quruq, salqin, yonuvchan...
    last_purchase_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    formula_items = relationship("ProductFormula", back_populates="raw_material")
    transactions = relationship("WarehouseTransaction", back_populates="raw_material")
    supplier_rel = relationship("Supplier", back_populates="materials")

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
    wholesale_price = Column(Float, nullable=True)  # ulgurji narx
    retail_price = Column(Float, nullable=True)  # chakana narx
    warehouse = Column(String(50), default="tayyor")  # qaysi omborda
    sector = Column(String(20), nullable=True)
    storage_conditions = Column(String(100), nullable=True)
    tags = Column(String(100), nullable=True)  # yangi, aksiya, import, mahalliy
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    formula_items = relationship("ProductFormula", back_populates="product")
    transactions = relationship("WarehouseTransaction", back_populates="product")
    orders = relationship("ProductionOrder", back_populates="product")
    sales = relationship("Sale", back_populates="product")
    units = relationship("ProductUnit", back_populates="product", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="product")

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
    source_warehouse = Column(String(50), nullable=True)  # kochirishda: qayerdan
    target_warehouse = Column(String(50), nullable=True)  # kochirishda: qayerga
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
    # Sifat nazorati (tayyor mahsulot chiqishida)
    qc_status = Column(String(20), default="kutilmoqda")  # kutilmoqda | qabul_qilingan | qisman | rad_etilgan
    qc_at = Column(DateTime, nullable=True)  # sifat nazorati o'tkazilgan vaqt
    accepted_qty = Column(Float, nullable=True)  # qabul qilingan miqdor
    rejected_qty = Column(Float, nullable=True)  # rad etilgan (brak) miqdor
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="orders")
    responsible = relationship("Employee", back_populates="orders")
    quality_acts = relationship("ProductionQC", back_populates="order")

class ProductionQC(Base):
    """Tayyor mahsulot sifat nazorati akti (raqamli dalolatnoma).

    Ishlab chiqarilgan partiya chiqishda tekshiriladi (TZ: "Chiqishda mahsulot
    sinovdan o'tkaziladi, natija raqamli dalolatnomaga yoziladi"):
    - qabul_qilingan: hammasi qabul (rejected=0)
    - qisman: bir qismi rad (rejected_qty ko'rsatiladi)
    - rad_etilgan: hammasi brak (rejected=quantity)

    Faqat qabul qilingan qismi sotiladigan "tayyor" omborga kiradi, rad etilgan
    qismi "brak" omboriga o'tadi (WarehouseTransaction PRODUCTION qatorlari orqali:
    +to'liq chiqim kirim, -rad etilgan chiqim).
    """
    __tablename__ = "production_qc"

    id = Column(Integer, primary_key=True, index=True)
    act_number = Column(String(50), unique=True, index=True)  # SQC-YYYYMM-NNNN
    order_id = Column(Integer, ForeignKey("production_orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity_checked = Column(Float, nullable=False)  # tekshirilgan miqdor
    accepted_qty = Column(Float, default=0.0)  # qabul qilingan
    rejected_qty = Column(Float, default=0.0)  # rad etilgan (brak)
    quality_status = Column(String(20), default="qabul_qilingan")
    photo_path = Column(String(255), nullable=True)  # sifat nazorati fotosurati
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)  # tekshiruvchi
    created_at = Column(DateTime, default=datetime.utcnow)

    # Aloqalar
    order = relationship("ProductionOrder", back_populates="quality_acts")
    product = relationship("Product")

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
    role = Column(String(30), default="ishchi")  # direktor, sotuvchi, kassir, omborchi, haydovchi, buxgalter, ishchi
    password_hash = Column(String(255), nullable=True)  # Web dashboard paroli (v3 auth)
    otp_secret = Column(String(64), nullable=True)      # Google Authenticator (TOTP) secret — base32 (v4.2 2FA)
    otp_enabled = Column(Boolean, default=False)        # 2FA yoqilganmi (v4.2)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    orders = relationship("ProductionOrder", back_populates="responsible")
    work_hours = relationship("WorkHours", back_populates="employee")
    salaries = relationship("SalaryPayment", back_populates="employee")

class WebSession(Base):
    """Web dashboard sessiyalari (refresh token + revoke qilish uchun).

    Access token HMAC'li va QISQA muddatli (SESSION_MINUTES, 5-30 daqiqa);
    refresh token shu jadvalda xeshlangan holda saqlanadi va har foydalanishda
    (sliding) muddati uzaytiriladi.

    Xavfsizlik qoidalari:
    - Logout'da sessiya revoke qilinadi — o'sha sessiyaga berilgan barcha darajalar
      (ruxsatlar) bekor bo'ladi (eski access ham refresh ham ishlamaydi).
    - Foydalanuvchi SESSION_IDLE_MINUTES dan uzoq harakatsiz tursa, sessiya
      "idle_timeout" bilan bekor qilinadi (qayta login talab qilinadi).
    - Parol o'zgarsa xodimning barcha sessiyalari bekor qilinadi.
    """
    __tablename__ = "web_sessions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    refresh_hash = Column(String(64), unique=True, nullable=False, index=True)  # sha256(hex)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)   # sliding muddat
    revoked_at = Column(DateTime, nullable=True)    # logout vaqti
    revoke_reason = Column(String(30), nullable=True)  # logout|expired|idle_timeout|admin|password_change
    last_seen_at = Column(DateTime, nullable=True)  # oxirgi so'rov vaqti (idle hisoblash uchun)
    last_used_at = Column(DateTime, nullable=True)  # oxirgi refresh vaqti
    user_agent = Column(String(250), nullable=True)

class EmployeeAuthSession(Base):
    """Telegram bot sessiyalari (v4: bot login/parol xavfsizligi).

    TZ: har bir xodim botda /login orqali PAROL bilan tasdiqlanadi va
    5-30 daqiqalik sessiya oladi. Sessiya tugaganda (muddat, idle) yoki
    logout qilinganda xodimga berilgan BARCHA darajalar (rol ruxsatlari)
    avtomatik bekor bo'ladi — keyingi buyruq uchun qayta /login kerak.
    """
    __tablename__ = "employee_auth_sessions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    telegram_id = Column(Integer, nullable=False, index=True)  # qaysi chat'da ochilgan
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False)      # BOT_SESSION_MINUTES (5-30 daq)
    last_activity = Column(DateTime, default=datetime.utcnow)  # idle hisoblash uchun
    revoked_at = Column(DateTime, nullable=True)       # logout / idle_timeout vaqti
    revoke_reason = Column(String(30), nullable=True)  # logout|expired|idle_timeout|admin|password_change
    logout_at = Column(DateTime, nullable=True)        # foydalanuvchi /logout bosgan vaqt

    employee = relationship("Employee")

class PasswordResetRequest(Base):
    """Web dashboard parol tiklash so'rovlari (self-service: so'rov -> admin tasdig'i)"""
    __tablename__ = "password_reset_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    phone_number = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)          # nima uchun so'raldi
    status = Column(String(20), default="pending")  # pending / approved / rejected / done / expired
    reset_hash = Column(String(64), nullable=True)   # tasdiqlangach beriladigan bir martalik kod xeshi
    code_expires_at = Column(DateTime, nullable=True)  # kod amal qilish muddati
    requested_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)     # admin ko'rib chiqqan vaqt
    reviewed_by = Column(Integer, nullable=True)      # admin xodim id
    completed_at = Column(DateTime, nullable=True)    # yangi parol o'rnatilgan vaqt

    # Aloqalar
    employee = relationship("Employee")

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
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0)
    paid_amount = Column(Float, default=0.0)  # sotuv paytida to'langan qism
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(100), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    payment_method = Column(String(30), default="cash")
    payment_methods = Column(String(100), nullable=True)  # cash+card+payme aralash
    is_credit = Column(Boolean, default=False)  # nasiya sotuvi
    credit_days = Column(Integer, default=0)  # nasiya muddati (kun)
    due_date = Column(DateTime, nullable=True)
    credit_status = Column(String(20), default="toliq_tolangan")
    sale_type = Column(String(20), default="retail")  # retail / wholesale
    returned_qty = Column(Float, default=0.0)  # qaytarilgan miqdor (qaytarish aktlari)
    returned_amount = Column(Float, default=0.0)  # qaytarilgan tovar qiymati
    status = Column(String(20), default="completed")
    sale_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, nullable=True, index=True)   # sotuvchi (telegram/web) id
    user_name = Column(String(100), nullable=True)          # sotuvchi ismi (reyting uchun)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="sales")
    customer = relationship("Customer", back_populates="sales")
    payments = relationship("Payment", back_populates="sale", cascade="all, delete-orphan")

class Customer(Base):
    """Mijozlar (CRM) jadvali"""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    company = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    credit_limit = Column(Float, default=0.0)  # nasiya limiti (so'm)
    total_debt = Column(Float, default=0.0)
    total_purchases = Column(Float, default=0.0)
    loyalty_points = Column(Float, default=0.0)
    is_wholesale = Column(Boolean, default=False)  # ulgurji mijoz
    status = Column(String(20), default="faol")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    sales = relationship("Sale", back_populates="customer")
    payments = relationship("Payment", back_populates="customer")
    reservations = relationship("Reservation", back_populates="customer")

class Payment(Base):
    """To'lovlar jadvali (aralash to'lov, nasiya to'lovi, qarz to'lovi)"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    amount = Column(Float, nullable=False)
    method = Column(String(30), nullable=False)  # cash, card, payme, click, transfer, credit
    payment_type = Column(String(20), default="sale")  # sale, debt, partial
    note = Column(String(255), nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    sale = relationship("Sale", back_populates="payments")
    customer = relationship("Customer", back_populates="payments")

class PaymentInvoice(Base):
    """Onlayn to'lov schyot-fakturasi (Click / Payme)
    
    Mijoz Click/Payme ilovasida to'laganda to'lovni kuzatish uchun.
    - Click: merchant_trans_id = invoice_id, prepare/complete webhook'lari
    - Payme: account.order_id = invoice_id, JSON-RPC webhook
    """
    __tablename__ = "payment_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String(50), unique=True, index=True, nullable=False)
    gateway = Column(String(20), nullable=False, default="click")  # click | payme
    amount = Column(Float, nullable=False)  # UZS
    status = Column(String(20), default="pending")  # pending | paid | cancelled | failed
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(100), nullable=True)
    note = Column(String(255), nullable=True)
    # Click tomonidan
    click_trans_id = Column(String(50), nullable=True)
    click_paydoc_id = Column(String(50), nullable=True)
    merchant_prepare_id = Column(String(50), nullable=True)
    merchant_confirm_id = Column(String(50), nullable=True)
    # Payme tomonidan
    payme_trans_id = Column(String(50), nullable=True)
    create_time = Column(Integer, nullable=True)  # payme ms
    perform_time = Column(Integer, nullable=True)
    cancel_time = Column(Integer, nullable=True)
    payme_state = Column(Integer, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    shop_order_id = Column(Integer, ForeignKey("shop_orders.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReturnAct(Base):
    """Qaytarish akti — mijoz mahsulotni qaytarganda (pul / almashtirish / bonus ball)

    Sotuv tarixiga "qaytarilgan" qayd etiladi, tovar omborga qaytadi,
    refund_type bo'yicha pul qaytariladi / boshqa mahsulotga almashtiriladi /
    bonus ball beriladi.
    """
    __tablename__ = "return_acts"

    id = Column(Integer, primary_key=True, index=True)
    act_number = Column(String(50), unique=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    customer_name = Column(String(100), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(100), nullable=True)
    unit = Column(String(20), nullable=True)
    quantity = Column(Float, nullable=False)  # qaytarilgan miqdor
    unit_price = Column(Float, nullable=False)  # sotuvdagi birlik narx
    total_amount = Column(Float, nullable=False)  # qaytarilgan tovar qiymati (X)
    reason = Column(String(30), default="mijoz_istagi")  # brak | notogri | mijoz_istagi
    refund_type = Column(String(20), nullable=False)  # cash | card | bonus | exchange
    refund_amount = Column(Float, default=0.0)  # mijozga qaytarilgan pul
    bonus_points = Column(Float, default=0.0)  # bonus turida berilgan ball
    debt_reduction = Column(Float, default=0.0)  # nasiya qarzidan hisobdan chiqarilgan qism
    # Almashtirish (exchange) ma'lumotlari
    exchange_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    exchange_product_name = Column(String(100), nullable=True)
    exchange_quantity = Column(Float, nullable=True)
    exchange_amount = Column(Float, default=0.0)  # yangi mahsulot qiymati (Y)
    tradein_amount = Column(Float, default=0.0)  # qaytarilgan qiymatdan hisobga olingan qism
    extra_amount = Column(Float, default=0.0)  # farq (Y>X bo'lsa mijoz qo'shimcha to'laydi)
    warehouse = Column(String(50), default="tayyor")  # qaytgan tovar ombori
    status = Column(String(20), default="completed")  # completed | rejected | cancelled
    note = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    sale = relationship("Sale")


class Delivery(Base):
    """Yetkazib berish topshirig'i — haydovchiga biriktiriladi (GPS kuzatuv bilan)

    Holatlar: yangi -> tayinlangan -> yo'lda -> yetkazildi | bekor
    """
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    delivery_number = Column(String(50), unique=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    customer_name = Column(String(100), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    customer_address = Column(String(255), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(100), nullable=True)
    unit = Column(String(20), nullable=True)
    quantity = Column(Float, nullable=False)  # yetkaziladigan miqdor
    driver_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    driver_name = Column(String(100), nullable=True)
    status = Column(String(20), default="tayinlangan")  # tayinlangan | yo'lda | yetkazildi | bekor
    # GPS kuzatuv
    start_lat = Column(Float, nullable=True)
    start_lng = Column(Float, nullable=True)
    current_lat = Column(Float, nullable=True)
    current_lng = Column(Float, nullable=True)
    last_location_at = Column(DateTime, nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    # v4.1: haydovchi "Muammo" tugmasi (yo'l yopiq, mijoz yo'q va h.k.)
    problem_reported = Column(String(255), nullable=True)
    problem_at = Column(DateTime, nullable=True)
    # v5: mijoz imzosi (TZ: "Yuk hujjatlari — barmoq izi / PIN bilan imzo")
    signature_name = Column(String(100), nullable=True)   # imzo qoldirgan shaxs
    signature_type = Column(String(20), default="pin")    # pin | fingerprint
    signature_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    sale = relationship("Sale")
    driver = relationship("Employee")
    locations = relationship("DeliveryLocation", back_populates="delivery",
                             cascade="all, delete-orphan")


class DebtReminder(Base):
    """Nasiya qarzi bo'yicha SMS eslatma — har bir muddat oralig'ida bir marta

    Sxema: muddati o'tganidan keyin 3 / 7 / 14 / 30 kunlik eslatmalar.
    (sale_id + day_bucket) unikal — qayta-qayta SMS yuborilmaydi.
    """
    __tablename__ = "debt_reminders"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    day_bucket = Column(Integer, nullable=False)  # 3 | 7 | 14 | 30
    status = Column(String(20), default="sent")  # sent | failed
    error = Column(String(255), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    sale = relationship("Sale")

    __table_args__ = (
        UniqueConstraint("sale_id", "day_bucket", name="uq_debt_reminder_sale_day"),
    )


class SlowStockAlert(Base):
    """Sekin sotiladigan (SLOW_STOCK_DAYS+ kun harakatlanmagan) zaxira ogohlantirishi

    - (item_type + item_id) unikal — tovar harakatga qaytmaguncha bitta ogohlantirish.
    - Tovar yana harakatlansa qayd o'chiriladi; yana N kun jim tursa qayta ogohlantiriladi.
    - status: sent (yuborilgan, qayta urinilmaydi) | failed (qayta uriniladi)
    """
    __tablename__ = "slow_stock_alerts"

    id = Column(Integer, primary_key=True, index=True)
    item_type = Column(String(20), nullable=False)  # product | raw
    item_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), default="sent")  # sent | failed
    error = Column(String(255), nullable=True)
    days_unmoved = Column(Integer, nullable=False)  # aniqlangan harakatsiz kunlar
    last_moved_at = Column(DateTime, nullable=True)  # oxirgi ombor harakati vaqti
    alert_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("item_type", "item_id", name="uq_slow_stock_item"),
    )


class TelegramBackupMessage(Base):
    """Telegram kanalga yuklangan backup hujjatlari — uzoq nusxalarni tozalash uchun

    Telegram Bot API kanal tarixini ro'yxatlay olmaydi, shuning uchun har bir
    yuborilgan backup xabarning message_id si shu yerda saqlanadi. Yuborilgan
    vaqti BACKUP_REMOTE_KEEP_DAYS dan oshgan xabarlar delete_message orqali
    o'chiriladi va qayd shu yerdan ham olib tashlanadi.
    """
    __tablename__ = "telegram_backup_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String(50), nullable=False, index=True)  # kanal ID yoki @nomi
    message_id = Column(Integer, nullable=False)
    filename = Column(String(200), nullable=True)  # yuborilgan fayl nomi
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)


class ShopOrder(Base):
    """Ommaviy web-do'kon buyurtmasi (catalog -> savat -> checkout)

    - method: cash (yetkazishda naqd) | click | payme
    - status: kutilmoqda (onlayn to'lov kutilyapti) | yakunlangan | bekor_qilingan
    - To'lov tasdiqlanganda/yoki cash buyurtmada darhol har bir qator
      Sale sifatida yoziladi (ombor va moliya yagona manba bo'lib qoladi).
    """
    __tablename__ = "shop_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False, index=True)
    address = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    method = Column(String(20), default="cash")  # cash | click | payme | mixed
    status = Column(String(20), default="kutilmoqda")  # kutilmoqda | yakunlangan | bekor_qilingan
    total_amount = Column(Float, default=0.0)
    online_amount = Column(Float, default=0.0)  # aralash/onlayn: to'lov xizmati orqali to'lanadigan qism
    cash_amount = Column(Float, default=0.0)    # aralash/naqd: yetkazishda to'lanadigan qism
    online_gateway = Column(String(10), nullable=True)  # click | payme (onlayn qismi qaysi xizmatda)
    invoice_id = Column(String(50), nullable=True)  # PaymentInvoice.invoice_id
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    customer = relationship("Customer")
    items = relationship("ShopOrderItem", back_populates="order",
                         cascade="all, delete-orphan")


class ShopOrderItem(Base):
    """Web-do'kon buyurtmasi qatori"""
    __tablename__ = "shop_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("shop_orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(100), nullable=True)
    unit = Column(String(20), nullable=True)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)  # quantity * unit_price

    # Aloqalar
    order = relationship("ShopOrder", back_populates="items")
    product = relationship("Product")


class CashShift(Base):
    """Kassir smenasi — naqd pul aylanmasini boshlash/yopish va farqni hisoblash

    Expected (kutilgan naqd) = boshlang'ich + smena davomidagi naqd kirimlar
    - naqd chiqimlar (qaytarish). Farq = haqiqiy sanalgan - kutilgan.
    """
    __tablename__ = "cash_shifts"

    id = Column(Integer, primary_key=True, index=True)
    shift_number = Column(String(50), unique=True, index=True)
    cashier_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    cashier_name = Column(String(100), nullable=True)
    opening_balance = Column(Float, default=0.0)  # boshlang'ich naqd (smena boshlanishi)
    expected_cash = Column(Float, nullable=True)  # yopilishda hisoblangan kutilgan naqd
    actual_cash = Column(Float, nullable=True)    # kassir sanagan haqiqiy naqd
    difference = Column(Float, nullable=True)     # actual - expected (+ ortiqcha / - kamomad)
    status = Column(String(20), default="ochiq")  # ochiq | yopilgan
    note = Column(Text, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow, index=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Aloqalar
    cashier = relationship("Employee")


class DeliveryLocation(Base):
    """Yetkazib berish GPS nuqtalari (haydovchi joylashuvini kuzatish)"""
    __tablename__ = "delivery_locations"

    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    source = Column(String(20), default="telegram")  # telegram | api
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    delivery = relationship("Delivery", back_populates="locations")


class Supplier(Base):
    """Yetkazib beruvchilar jadvali"""
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)
    contact_person = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    rating = Column(Float, default=5.0)  # 1-5, sifat bo'yicha avtomatik
    on_time_count = Column(Integer, default=0)
    late_count = Column(Integer, default=0)
    total_debt = Column(Float, default=0.0)  # ularga qarzimiz (schyot-faktura)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aloqalar
    materials = relationship("RawMaterial", back_populates="supplier_rel")
    deliveries = relationship("SupplierDelivery", back_populates="supplier")

class SupplierDelivery(Base):
    """Yetkazib beruvchidan qabul qilish akti (sifat nazorati bilan)"""
    __tablename__ = "supplier_deliveries"
    
    id = Column(Integer, primary_key=True, index=True)
    act_number = Column(String(50), unique=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    quantity_ordered = Column(Float, nullable=False)  # buyurtma qilingan
    quantity_received = Column(Float, nullable=False)  # tarozida chiqqan
    quality_status = Column(String(20), default="qabul_qilingan")  # qabul/rad/qisman
    price_per_unit = Column(Float, default=0.0)
    deficiency_amount = Column(Float, default=0.0)  # kamomad summa
    photo_path = Column(String(255), nullable=True)  # sifat nazorati fotosurati
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    supplier = relationship("Supplier", back_populates="deliveries")
    raw_material = relationship("RawMaterial")

class ProductUnit(Base):
    """Mahsulot o'lchov birliklari konvertatsiyasi (1 pallet = 40 qop = 2000 kg)"""
    __tablename__ = "product_units"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit = Column(String(20), nullable=False)
    factor = Column(Float, default=1.0)  # asosiy birlikka nisbati (1 qop = 50 kg -> factor 50)
    base_unit = Column(String(20), nullable=False)  # asosiy birlik (kg)
    price = Column(Float, nullable=True)  # shu birlikdagi narx (ulgurji/chakana)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="units")
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class Reservation(Base):
    """Rezervatsiya jadvali — mahsulotni vaqtincha bloklash"""
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    reservation_code = Column(String(50), unique=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(100), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    status = Column(String(20), default="faol")  # faol, yakunlangan, bekor, yechilgan
    expires_at = Column(DateTime, nullable=False)  # avtomatik yechilish vaqti
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    product = relationship("Product", back_populates="reservations")
    customer = relationship("Customer", back_populates="reservations")

class InventoryCheck(Base):
    """Inventarizatsiya varaqasi — sanab chiqish va farq aniqlash"""
    __tablename__ = "inventory_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    check_number = Column(String(50), unique=True, index=True)
    warehouse = Column(String(50), default="asosiy")
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    system_quantity = Column(Float, default=0.0)
    actual_quantity = Column(Float, default=0.0)
    difference = Column(Float, default=0.0)  # yetishmovchilik (-) yoki ortiqcha (+)
    reason = Column(String(100), nullable=True)  # ogirlik, sinish, xato, ogirlik
    act_created = Column(Boolean, default=False)  # yetishmovchilik dalolatnomasi yaratildimi
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Aloqalar
    raw_material = relationship("RawMaterial")
    product = relationship("Product")

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
    extra_data = Column("metadata", JSON, nullable=True)  # Qo'shimcha ma'lumotlar
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


class FuelLog(Base):
    """Yoqilg'i nazorati — haydovchi har yonilg'i quyishni qayd etadi (TZ: D-bo'lim)

    Tizim har bir haydovchi uchun "1 km ga qancha yoqilg'i ketgan"ni hisoblaydi;
    me'yordan (litr/100km) oshsa direktor xabar oladi.
    """
    __tablename__ = "fuel_logs"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    driver_name = Column(String(100), nullable=True)
    vehicle = Column(String(50), nullable=True)          # mashina raqami / nomi
    odometer_km = Column(Float, nullable=True)          # quyish vaqtidagi spidometr
    prev_odometer_km = Column(Float, nullable=True)     # oldingi quyishdagi ko'rsatkich
    liters = Column(Float, nullable=False)              # quyilgan litr
    price_per_liter = Column(Float, nullable=True)      # narx (so'm/l)
    total_cost = Column(Float, nullable=True)           # jami xarajat
    note = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    driver = relationship("Employee")


class ExpenseReport(Base):
    """Avans hisoboti / xodim xarajati (TZ: "Avans hisoboti")

    Xodim (masalan haydovchi) yo'l haqi, benzin, ovqat uchun sarflagan pullarini
    qayd etadi; direktor tasdiqlaydi. Tasdiqlangan xarajat kunlik/moliyaviy
    hisobotga qo'shiladi.
    """
    __tablename__ = "expense_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_number = Column(String(50), unique=True, index=True)  # EXP-YYYYMM-NNNN
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    employee_name = Column(String(100), nullable=True)
    category = Column(String(30), default="boshqa")  # yoqilgi | yol_hagi | ovqat | benzin | boshqa
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="kutilmoqda")  # kutilmoqda | tasdiqlangan | rad_etilgan
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    employee = relationship("Employee")


class SuspiciousActivity(Base):
    """Shubhali harakat detektori — anomaliyalarni kuzatish (TZ: Xavfsizlik)

    Misol: tunda (23:00-06:00) qilingan katta sotuv, bir vaqtning o'zida
    ikki qurilmadan kirish, 20% dan yuqori chegirma, qaytarish ko'payishi.
    """
    __tablename__ = "suspicious_activities"

    id = Column(Integer, primary_key=True, index=True)
    activity_type = Column(String(50), nullable=False)  # night_sale | big_discount | double_login | many_returns | fuel_anomaly
    severity = Column(String(10), default="medium")    # low | medium | high
    description = Column(Text, nullable=True)
    user_name = Column(String(100), nullable=True)
    user_id = Column(Integer, nullable=True)
    entity_id = Column(Integer, nullable=True)           # qaysi yozuv (sale id va h.k.)
    status = Column(String(20), default="yangi")       # yangi | ko'rib_chiqilgan | hal_qilingan
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PickingList(Base):
    """Yig'ish varaqasi (Picking list) — omborchi uchun buyurtma bo'yicha ro'yxat (TZ: 4-modul)

    Sotuv/shop buyurtmasi uchun omborchi qancha mahsulotni qayerdan (sektor)
    yig'ishi ko'rsatiladi. Yuk tayyorlangach status 'tayyor'ga o'tadi.
    """
    __tablename__ = "picking_lists"

    id = Column(Integer, primary_key=True, index=True)
    picking_number = Column(String(50), unique=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True, index=True)
    shop_order_id = Column(Integer, ForeignKey("shop_orders.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    product_name = Column(String(100), nullable=True)
    unit = Column(String(20), nullable=True)
    quantity = Column(Float, nullable=False)
    sector = Column(String(20), nullable=True)      # ombordagi sektor (A1, B2...)
    status = Column(String(20), default="yangi")   # yangi | tayyor | yuborilgan
    picked_by = Column(String(100), nullable=True)
    picked_at = Column(DateTime, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    product = relationship("Product")

class ProductPriceHistory(Base):
    """Mahsulot narx tarixi (TZ: "Sana bo'yicha narx tarixi")

    Har bir narx o'zgarishi yangi qator sifatida saqlanadi — eski narx
    o'chirilmaydi, shuning uchun istalgan sanada kimga qanday narxda
    sotilgani/bo'lgani ko'rinadi.
    """
    __tablename__ = "product_price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    product_name = Column(String(100), nullable=True)      # nom o'zgarsa ham tarix tushunarli
    old_price = Column(Float, nullable=True)
    new_price = Column(Float, nullable=False)
    price_type = Column(String(20), default="selling")    # selling | wholesale | retail | cost
    reason = Column(String(100), nullable=True)            # "Aksiya", "Direktor qarori"...
    changed_by = Column(String(100), nullable=True)        # kim o'zgartirgan
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Aloqalar
    product = relationship("Product")


class Warehouse(Base):
    """Omborlar katalogi (TZ: Warehouses — ombor CRUD)

    Tizim 3 turdagi ombor bilan ishlaydi: xomashyo, tayyor mahsulot, brak.
    Har bir omborning manzili, mas'uli, sektorlari va holati shu yerda.
    """
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    warehouse_type = Column(String(30), default="tayyor")  # xomashyo | tayyor | brak | asosiy
    address = Column(String(255), nullable=True)
    manager_name = Column(String(100), nullable=True)      # mas'ul xodim
    sectors = Column(String(100), nullable=True)           # "A1,B2,C3" — ombor xaritasi
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =====================================================
# AVTOMATIK SCHEMA MIGRATSIYA (eski construction.db ga)
# Yangi ustunlar/jadvallarni qo'shadi, ma'lumot o'chirilmaydi
# =====================================================

# Jadvalga qo'shiladigan yangi ustunlar: {table: [(column, ddl_type), ...]}
EXTRA_COLUMNS = {
    "raw_materials": [
        ("supplier_id", "INTEGER"),
        ("warehouse", "VARCHAR(50)"),
        ("sector", "VARCHAR(20)"),
        ("storage_conditions", "VARCHAR(100)"),
    ],
    "products": [
        ("wholesale_price", "FLOAT"),
        ("retail_price", "FLOAT"),
        ("warehouse", "VARCHAR(50)"),
        ("sector", "VARCHAR(20)"),
        ("storage_conditions", "VARCHAR(100)"),
        ("tags", "VARCHAR(100)"),
    ],
    "warehouse_transactions": [
        ("source_warehouse", "VARCHAR(50)"),
        ("target_warehouse", "VARCHAR(50)"),
    ],
    "employees": [
        ("role", "VARCHAR(30)"),
        ("password_hash", "VARCHAR(255)"),
        ("otp_secret", "VARCHAR(64)"),
        ("otp_enabled", "BOOLEAN"),
    ],
    "deliveries": [
        ("problem_reported", "VARCHAR(255)"),
        ("problem_at", "DATETIME"),
        ("signature_name", "VARCHAR(100)"),
        ("signature_type", "VARCHAR(20)"),
        ("signature_at", "DATETIME"),
    ],
    "web_sessions": [
        ("revoke_reason", "VARCHAR(30)"),
        ("last_seen_at", "DATETIME"),
    ],
    "sales": [
        ("user_id", "INTEGER"),
        ("user_name", "VARCHAR(100)"),
        ("discount_amount", "FLOAT"),
        ("paid_amount", "FLOAT"),
        ("customer_id", "INTEGER"),
        ("payment_methods", "VARCHAR(100)"),
        ("is_credit", "BOOLEAN"),
        ("credit_days", "INTEGER"),
        ("due_date", "DATETIME"),
        ("credit_status", "VARCHAR(20)"),
        ("sale_type", "VARCHAR(20)"),
        ("returned_qty", "FLOAT"),
        ("returned_amount", "FLOAT"),
    ],
    "payment_invoices": [
        ("shop_order_id", "INTEGER"),
    ],
    "production_orders": [
        ("qc_status", "VARCHAR(20)"),
        ("qc_at", "DATETIME"),
        ("accepted_qty", "FLOAT"),
        ("rejected_qty", "FLOAT"),
    ],
    "shop_orders": [
        ("online_amount", "FLOAT"),
        ("cash_amount", "FLOAT"),
        ("online_gateway", "VARCHAR(10)"),
    ],
}


def upgrade_schema(bind=None):
    """
    Mavjud SQLite database'ga yangi ustunlarni xavfsiz qo'shadi.
    Bu eski construction.db faylini o'chirmasdan yangilash uchun kerak.
    (create_all yangi ustunlarni eski jadvalga qo'sha olmaydi)
    """
    target = bind or engine

    try:
        # 1) Yangi jadvallarni yaratish (barcha dialect'larda)
        Base.metadata.create_all(bind=target)

        # 2) SQLite'da eski jadvallarga yangi ustunlarni qo'shish
        if target.dialect.name != "sqlite":
            return
        inspector = inspect(target)
        with target.begin() as conn:
            for table_name, columns in EXTRA_COLUMNS.items():
                if table_name not in inspector.get_table_names():
                    continue
                existing = {c["name"] for c in inspector.get_columns(table_name)}
                for col_name, col_type in columns:
                    if col_name not in existing:
                        conn.execute(text(
                            f'ALTER TABLE "{table_name}" ADD COLUMN {col_name} {col_type}'
                        ))
                        logger.info(f"Migratsiya: {table_name}.{col_name} qo'shildi")
    except Exception as e:
        logger.error(f"Schema migratsiyada xatolik: {e}")


# Jadvalarni yaratish
def create_tables():
    """Database jadvallarini yaratish va eski DB ni yangilash"""
    upgrade_schema()
    print("Database tables created/updated successfully")


if __name__ == "__main__":
    create_tables()