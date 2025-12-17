# database/__init__.py

# CRUD operatsiyalari
from .crud import (
    # Raw materials
    create_raw_material,
    get_raw_material,
    update_raw_material,
    delete_raw_material,
    check_low_stock_materials,
    
    # Products
    create_product,
    get_product,
    get_products_by_category,
    
    # Production
    create_production_order,
    
    # Employees
    create_employee,
    get_employee_by_telegram_id,
    get_employees_by_department,
    add_work_hours,
    get_employee_work_hours,
    create_salary_payment,
    get_employee_salary_payments,
    
    # Sales (yangi qo'shilgan)
    create_sale,
    get_sale_by_id,
    get_sales_by_period,
    create_sale_item,
    
    # Customers (yangi qo'shilgan)
    create_customer,
    get_customer_by_phone,
    
    # Statistics
    get_warehouse_statistics,
    get_production_statistics,
    get_financial_statistics,
    get_sales_statistics,
    
    # Notifications
    create_notification,
    get_pending_notifications,
    mark_notification_sent
)

# Session
from .session import get_db, Base, engine, SessionLocal

# Models
from .models import (
    # Base models
    BaseModel,
    
    # Domain models
    RawMaterial,
    Product,
    ProductFormula,
    WarehouseTransaction,
    ProductionOrder,
    ProductionItem,
    Employee,
    WorkHours,
    SalaryPayment,
    Sale,
    SaleItem,
    Customer,
    Notification
)

__all__ = [
    # CRUD functions
    "create_raw_material",
    "get_raw_material",
    "update_raw_material",
    "delete_raw_material",
    "check_low_stock_materials",
    "create_product",
    "get_product",
    "get_products_by_category",
    "create_production_order",
    "create_employee",
    "get_employee_by_telegram_id",
    "get_employees_by_department",
    "add_work_hours",
    "get_employee_work_hours",
    "create_salary_payment",
    "get_employee_salary_payments",
    "create_sale",
    "get_sale_by_id",
    "get_sales_by_period",
    "create_sale_item",
    "create_customer",
    "get_customer_by_phone",
    "get_warehouse_statistics",
    "get_production_statistics",
    "get_financial_statistics",
    "get_sales_statistics",
    "create_notification",
    "get_pending_notifications",
    "mark_notification_sent",
    
    # Database session
    "get_db",
    "Base",
    "engine",
    "SessionLocal",
    
    # Models
    "BaseModel",
    "RawMaterial",
    "Product",
    "ProductFormula",
    "WarehouseTransaction",
    "ProductionOrder",
    "ProductionItem",
    "Employee",
    "WorkHours",
    "SalaryPayment",
    "Sale",
    "SaleItem",
    "Customer",
    "Notification"
]