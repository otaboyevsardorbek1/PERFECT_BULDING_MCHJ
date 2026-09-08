"""
REST API v5 — construction_factory_bot.md "API METODLARI RO'YXATI" (2-bo'lim)
bo'yicha to'liq spec-ga mos endpointlar.

Auth (login/logout/refresh/profile/register/verify-2fa), Users, Products,
Categories, Customers, Orders, Payments, Inventory, Deliveries (imzo),
Reports, Suppliers, Production, Warehouses va Narx tarixi.
"""
from datetime import datetime, timedelta, date
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import models, crud, crud_v5
from database.session import get_db
from dashboard.auth import (
    AuthUser, PASSWORD_MIN_LENGTH, create_web_session, employee_2fa_enabled,
    find_employee_by_phone, get_current_user, hash_password, issue_2fa_pending_token,
    refresh_session, require_any_edit, require_role, revoke_session,
    set_employee_password, user_to_dict, verify_2fa_code, verify_password,
    effective_role, get_role_label,
)
from config import ROLES

router = APIRouter(prefix="/api", tags=["v5"])


def require_any_view_v5(modules):
    """Kamida bitta modulni ko'rish huquqini talab qiluvchi dependency."""
    def dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        from config import role_can_view
        if not any(role_can_view(user.role, m) for m in modules):
            raise HTTPException(
                status_code=403,
                detail=f"Ruxsat yo'q: ({', '.join(modules)}) huquqlaridan biri kerak.",
            )
        return user
    return dep


def _parse_day(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(400, "Sana format: YYYY-MM-DD")


def _period_range(days: int) -> tuple:
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    return start, end


def _report_stats(db: Session, start: datetime, end: datetime) -> Dict:
    sales = db.query(models.Sale).filter(
        models.Sale.sale_date >= start, models.Sale.sale_date <= end
    ).all()
    total_amount = sum(float(s.total_amount or 0) for s in sales)
    paid = sum(float(s.paid_amount or 0) for s in sales)
    discount = sum(float(s.discount_amount or 0) for s in sales)
    credit_sales = [s for s in sales if s.is_credit]
    payments = db.query(models.Payment).filter(
        models.Payment.created_at >= start, models.Payment.created_at <= end
    ).all()
    by_method = {}
    for p in payments:
        by_method[p.method] = by_method.get(p.method, 0) + float(p.amount or 0)
    products_sold = db.query(models.Sale.product_id, func.sum(models.Sale.quantity)).filter(
        models.Sale.sale_date >= start, models.Sale.sale_date <= end
    ).group_by(models.Sale.product_id).order_by(desc(func.sum(models.Sale.quantity))).first()
    top_product = None
    if products_sold and products_sold[0]:
        prod = db.query(models.Product).filter(models.Product.id == products_sold[0]).first()
        top_product = {"id": products_sold[0], "name": prod.name if prod else None,
                       "quantity": float(products_sold[1] or 0)}
    return {
        "sales_count": len(sales),
        "total_amount": round(total_amount, 0),
        "paid_amount": round(paid, 0),
        "discount_amount": round(discount, 0),
        "credit_amount": round(sum(float(s.total_amount - (s.paid_amount or 0)) for s in credit_sales), 0),
        "credit_sales_count": len(credit_sales),
        "payments": round(sum(float(p.amount or 0) for p in payments), 0),
        "payments_by_method": {k: round(v, 0) for k, v in by_method.items()},
        "top_product": top_product,
    }


# ================= AVTORIZATSIYA (spec: /api/auth/*) =================
@router.post("/auth/login")
def api_auth_login(request: Request, data: dict, db: Session = Depends(get_db)):
    """Spec alias: POST /api/auth/login (asosiy login: /api/login)."""
    from dashboard.api_v3 import api_login
    return api_login(request, data, db)


@router.post("/auth/logout")
def api_auth_logout(request: Request, data: dict = None, db: Session = Depends(get_db)):
    """Spec alias: POST /api/auth/logout."""
    from dashboard.api_v3 import api_logout
    return api_logout(request, data, db)


@router.post("/auth/refresh")
def api_auth_refresh(data: dict, db: Session = Depends(get_db)):
    """Spec alias: POST /api/auth/refresh."""
    from dashboard.api_v3 import api_refresh
    return api_refresh(data, db)


@router.get("/auth/profile")
def api_auth_profile(db: Session = Depends(get_db),
                     user: AuthUser = Depends(get_current_user)):
    """Spec: GET /api/auth/profile — joriy foydalanuvchi ma'lumotlari."""
    return {"user": user.to_dict()}


@router.put("/auth/profile")
def api_auth_update_profile(data: dict, db: Session = Depends(get_db),
                            user: AuthUser = Depends(get_current_user)):
    """Spec: PUT /api/auth/profile — o'z profilini tahrirlash."""
    allowed = {"full_name", "phone_number", "position", "department",
               "bank_account", "address", "notes", "hourly_rate"}
    payload = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not payload:
        raise HTTPException(400, "O'zgartiriladigan maydon yo'q")
    if "phone_number" in payload:
        existing = find_employee_by_phone(db, str(payload["phone_number"]))
        if existing and existing.id != user.id:
            raise HTTPException(400, "Bu telefon raqam boshqa xodimda band")
    emp = crud_v5.update_employee(db, user.id, payload)
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action="API: profil tahrirlandi", module="security")
    return {"user": user_to_dict(emp)}


@router.post("/auth/verify-2fa")
def api_auth_verify_2fa(data: dict, db: Session = Depends(get_db)):
    """Spec: POST /api/auth/verify-2fa — ikki bosqichli tasdiq kodini tekshirish.

    {phone, otp_code} yoki {employee_id, otp_code} qabul qiladi.
    """
    otp_code = str(data.get("otp_code", "")).strip()
    if not otp_code:
        raise HTTPException(400, "otp_code kerak")
    employee = None
    if data.get("employee_id"):
        employee = db.query(models.Employee).filter(
            models.Employee.id == int(data["employee_id"])).first()
    else:
        phone = str(data.get("phone", "")).strip()
        if not phone:
            raise HTTPException(400, "phone yoki employee_id kerak")
        employee = find_employee_by_phone(db, phone)
    if not employee:
        raise HTTPException(404, "Xodim topilmadi")
    if not employee_2fa_enabled(employee):
        return {"success": True, "verified": False, "reason": "2fa_off"}
    if verify_2fa_code(employee, otp_code):
        return {"success": True, "verified": True}
    raise HTTPException(401, "Kod noto'g'ri")


# ================= XODIMLAR / USERS (spec: /api/users) =================
def _can_manage_users(user: AuthUser) -> bool:
    return user.role in ("direktor", "admin") or user.is_admin


@router.get("/users")
def api_users(db: Session = Depends(get_db),
              user: AuthUser = Depends(require_role("admin"))):
    """Spec: GET /api/users — barcha xodimlar."""
    status = None
    employees = crud_v5.list_employees(db, status=status)
    return {"users": [crud_v5.employee_to_dict(e) for e in employees]}


@router.get("/users/{employee_id}")
def api_user(employee_id: int, db: Session = Depends(get_db),
             user: AuthUser = Depends(require_role("admin"))):
    emp = crud_v5.get_employee(db, employee_id)
    if not emp:
        raise HTTPException(404, "Xodim topilmadi")
    return {"user": crud_v5.employee_to_dict(emp)}


@router.post("/users")
def api_create_user(data: dict, db: Session = Depends(get_db),
                    user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: POST /api/users — yangi xodim qo'shish (Direktor)."""
    full_name = str(data.get("full_name", "")).strip()
    phone = str(data.get("phone_number", "")).strip()
    role = str(data.get("role", "ishchi")).strip()
    if not full_name or not phone:
        raise HTTPException(400, "full_name va phone_number kerak")
    if role not in ROLES:
        raise HTTPException(400, f"role: {', '.join(ROLES.keys())} dan bo'lishi kerak")
    if find_employee_by_phone(db, phone):
        raise HTTPException(400, "Bu telefon raqam band")
    payload = {
        "full_name": full_name,
        "phone_number": phone,
        "position": data.get("position", role),
        "department": data.get("department", "Asosiy"),
        "role": role,
        "salary": float(data.get("salary", 0) or 0),
        "hourly_rate": float(data.get("hourly_rate", 0) or 0),
        "bank_account": data.get("bank_account"),
        "address": data.get("address"),
        "hire_date": datetime.utcnow(),
        "status": crud_v5.parse_employee_status(data.get("status", "faol")),
    }
    emp = crud.create_employee(db, payload)
    if data.get("password"):
        try:
            set_employee_password(db, emp, str(data["password"]))
        except ValueError as e:
            raise HTTPException(400, str(e))
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: xodim qo'shildi ({full_name})", module="admin")
    return {"user": crud_v5.employee_to_dict(emp)}


@router.put("/users/{employee_id}")
def api_update_user(employee_id: int, data: dict, db: Session = Depends(get_db),
                    user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: PUT /api/users/{id} — xodim ma'lumotlarini tahrirlash."""
    emp = crud_v5.get_employee(db, employee_id)
    if not emp:
        raise HTTPException(404, "Xodim topilmadi")
    allowed = {"full_name", "phone_number", "position", "department", "role",
               "salary", "hourly_rate", "bank_account", "address", "notes",
               "is_admin", "passport_data"}
    payload = {}
    for k, v in data.items():
        if k in allowed and v is not None:
            if k == "is_admin":
                payload[k] = bool(v)
            else:
                payload[k] = v
    if "role" in payload and payload["role"] not in ROLES:
        raise HTTPException(400, f"role: {', '.join(ROLES.keys())} dan bo'lishi kerak")
    if "phone_number" in payload:
        existing = find_employee_by_phone(db, str(payload["phone_number"]))
        if existing and existing.id != employee_id:
            raise HTTPException(400, "Bu telefon raqam band")
    updated = crud_v5.update_employee(db, employee_id, payload)
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: xodim tahrirlandi (#{employee_id})", module="admin")
    return {"user": crud_v5.employee_to_dict(updated)}


@router.put("/users/{employee_id}/status")
def api_update_user_status(employee_id: int, data: dict, db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: PUT /api/users/{id}/status — faollikni o'zgartirish (faol|bloklangan|ishdan_ketgan)."""
    status = str(data.get("status", "")).strip()
    valid = ("faol", "bloklangan", "ishdan_ketgan", "ta'tilda", "dam_olish")
    if status not in valid:
        raise HTTPException(400, f"status: {', '.join(valid)}")
    emp = crud_v5.set_employee_status(db, employee_id, status)
    if not emp:
        raise HTTPException(404, "Xodim topilmadi")
    return {"success": True, "status": status}


@router.delete("/users/{employee_id}")
def api_delete_user(employee_id: int, db: Session = Depends(get_db),
                    user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: DELETE /api/users/{id} — xodimni o'chirish."""
    if employee_id == user.id:
        raise HTTPException(400, "O'zingizni o'chira olmaysiz")
    if not crud_v5.delete_employee(db, employee_id):
        raise HTTPException(404, "Xodim topilmadi")
    return {"success": True}


@router.put("/users/{employee_id}/password")
def api_set_user_password(employee_id: int, data: dict, db: Session = Depends(get_db),
                          user: AuthUser = Depends(require_role("admin", edit=True))):
    """Direktor xodim parolini o'rnatadi (parol o'zgarsa sessiyalar bekor bo'ladi)."""
    password = str(data.get("password", ""))
    emp = crud_v5.get_employee(db, employee_id)
    if not emp:
        raise HTTPException(404, "Xodim topilmadi")
    try:
        set_employee_password(db, emp, password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


# ================= MAHSULOTLAR (spec: /api/products) =================
def product_to_dict(p: models.Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "unit": p.unit,
        "selling_price": p.selling_price,
        "wholesale_price": p.wholesale_price,
        "retail_price": p.retail_price,
        "production_cost": p.production_cost,
        "profit_margin": p.profit_margin,
        "barcode": p.barcode,
        "description": p.description,
        "image_url": p.image_url,
        "is_active": bool(p.is_active),
        "warehouse": p.warehouse,
        "sector": p.sector,
        "storage_conditions": p.storage_conditions,
        "tags": p.tags,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/products")
def api_v5_products(q: Optional[str] = None, category: Optional[str] = None,
                    is_active: Optional[bool] = None, limit: int = 500,
                    db: Session = Depends(get_db),
                    user: AuthUser = Depends(require_any_view_v5(["production", "warehouse", "sales"]))):
    """Spec: GET /api/products — filtr + pagination + qidiruv."""
    query = db.query(models.Product)
    if q:
        like = f"%{q}%"
        query = query.filter(models.Product.name.ilike(like))
    if category:
        query = query.filter(models.Product.category == category)
    if is_active is not None:
        query = query.filter(models.Product.is_active.is_(is_active))
    products = query.order_by(models.Product.name).limit(limit).all()
    result = []
    for p in products:
        d = product_to_dict(p)
        d["available_qty"] = crud.get_available_product_qty(db, p.id)
        result.append(d)
    return {"products": result}


@router.get("/products/search")
def api_products_search(q: str = Query(..., min_length=1), limit: int = 20,
                        db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("production"))):
    """Spec: GET /api/products/search — tez qidiruv."""
    like = f"%{q}%"
    products = db.query(models.Product).filter(
        models.Product.name.ilike(like)
    ).limit(limit).all()
    return {"products": [product_to_dict(p) for p in products]}


@router.get("/products/low-stock")
def api_products_low_stock(min_stock: Optional[float] = None,
                           db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_role("production"))):
    """Spec: GET /api/products/low-stock — zaxirasi kam mahsulotlar."""
    result = []
    for p in db.query(models.Product).filter(models.Product.is_active.is_(True)).all():
        qty = crud.get_available_product_qty(db, p.id)
        if qty <= 0 or (min_stock is not None and qty < min_stock):
            d = product_to_dict(p)
            d["available_qty"] = qty
            result.append(d)
    return {"products": result}


@router.get("/products/top-selling")
def api_products_top_selling(days: int = 30, limit: int = 10,
                             db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("production"))):
    """Spec: GET /api/products/top-selling — eng ko'p sotilganlar."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        models.Sale.product_id,
        func.sum(models.Sale.quantity).label("qty"),
        func.sum(models.Sale.total_amount).label("total"),
    ).filter(models.Sale.sale_date >= since).group_by(
        models.Sale.product_id
    ).order_by(desc(func.sum(models.Sale.quantity))).limit(limit).all()
    result = []
    for r in rows:
        prod = db.query(models.Product).filter(models.Product.id == r.product_id).first()
        result.append({
            "product_id": r.product_id,
            "product_name": prod.name if prod else None,
            "quantity": round(float(r.qty or 0), 1),
            "total": round(float(r.total or 0), 0),
        })
    return {"products": result}


@router.post("/products")
def api_create_product(data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["production", "warehouse"]))):
    """Spec: POST /api/products — mahsulot qo'shish."""
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(400, "name kerak")
    if db.query(models.Product).filter(models.Product.name == name).first():
        raise HTTPException(400, "Bunday mahsulot mavjud")
    allowed = {c.name for c in models.Product.__table__.columns} - {"id", "created_at", "updated_at"}
    payload = {k: v for k, v in data.items() if k in allowed}
    payload["name"] = name
    try:
        product = crud.create_product(db, payload)
    except Exception as e:
        raise HTTPException(400, str(e))
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: mahsulot qo'shildi ({name})", module="production")
    return {"product": product_to_dict(product)}


@router.put("/products/{product_id}")
def api_update_product(product_id: int, data: dict, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_any_edit(["production", "warehouse"]))):
    """Spec: PUT /api/products/{id} — mahsulot tahrirlash."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Mahsulot topilmadi")
    allowed = {c.name for c in models.Product.__table__.columns} - {
        "id", "created_at", "updated_at", "selling_price", "wholesale_price",
        "retail_price", "production_cost"}
    payload = {k: v for k, v in data.items() if k in allowed}
    for k, v in payload.items():
        setattr(product, k, v)
    db.commit()
    db.refresh(product)
    return {"product": product_to_dict(product)}


@router.put("/products/{product_id}/price")
def api_update_product_price(product_id: int, data: dict, db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: PUT /api/products/{id}/price — narxni o'zgartirish (narx tarixiga yoziladi)."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Mahsulot topilmadi")
    price_type = str(data.get("price_type", "selling")).strip()
    new_price = float(data.get("new_price", data.get("price", 0)))
    if new_price < 0:
        raise HTTPException(400, "Narx manfiy bo'lishi mumkin emas")
    crud_v5.record_price_change(
        db, product, new_price, price_type=price_type,
        reason=data.get("reason"), changed_by=user.full_name,
    )
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: {product.name} narxi o'zgartirildi", module="production")
    return {"product": product_to_dict(product), "price_type": price_type, "new_price": new_price}


@router.put("/products/{product_id}/stock")
def api_update_product_stock(product_id: int, data: dict, db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("warehouse", edit=True))):
    """Spec: PUT /api/products/{id}/stock — qoldiqni tuzatish (audit qilinadi)."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Mahsulot topilmadi")
    delta = float(data.get("delta", data.get("quantity", 0)))
    if delta == 0:
        raise HTTPException(400, "delta 0 dan farqli bo'lishi kerak")
    note = str(data.get("reason") or data.get("notes") or "Qoldiq tuzatish")
    tr = models.WarehouseTransaction(
        product_id=product_id,
        quantity=delta,
        transaction_type=models.TransactionType.INVENTORY,
        user_id=user.telegram_id or 0,
        user_name=user.full_name,
        document_number=f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        notes=note,
    )
    db.add(tr)
    db.commit()
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: {product.name} qoldig'i tuzatildi ({delta})", module="warehouse")
    return {"success": True, "delta": delta,
            "available_qty": crud.get_available_product_qty(db, product_id)}


@router.post("/products/import")
def api_import_products(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: POST /api/products/import — Excel/JSON orqali ommaviy yuklash.

    JSON: {"products": [{name, category, unit, selling_price, ...}, ...]}
    Excel (.xlsx) fayl yuborilsa ham shu formatga aylantiriladi.
    """
    import io
    items = data.get("products") or data.get("items")
    if items is None:
        raise HTTPException(400, "products ro'yxati kerak (JSON)")
    created, updated, errors = 0, 0, []
    for idx, item in enumerate(items, start=1):
        try:
            name = str(item.get("name", "")).strip()
            if not name:
                raise ValueError("name bo'sh")
            existing = db.query(models.Product).filter(models.Product.name == name).first()
            allowed = {c.name for c in models.Product.__table__.columns} - {"id", "created_at", "updated_at"}
            payload = {k: v for k, v in item.items() if k in allowed}
            payload["name"] = name
            if existing:
                for k, v in payload.items():
                    if k != "name":
                        setattr(existing, k, v)
                updated += 1
            else:
                db.add(models.Product(**payload))
                db.flush()  # keyingi qator bilan takror bo'lmasligi uchun darhol ko'rinadi
                created += 1
        except Exception as e:
            errors.append({"row": idx, "error": str(e)})
    db.commit()
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: mahsulotlar import ({created} yangi, {updated} yangilandi)",
                           module="production")
    return {"success": True, "created": created, "updated": updated, "errors": errors}


@router.get("/products/{product_id}/price-history")
def api_product_price_history(product_id: int, limit: int = 50,
                              db: Session = Depends(get_db),
                              user: AuthUser = Depends(require_role("production"))):
    """TZ: Sana bo'yicha narx tarixi — bitta mahsulot uchun."""
    return {"price_history": crud_v5.list_price_history(db, product_id=product_id, limit=limit)}


@router.get("/price-history")
def api_price_history(product_id: Optional[int] = None, price_type: Optional[str] = None,
                      limit: int = 100, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_role("production"))):
    """TZ: Sana bo'yicha narx tarixi — barcha mahsulotlar bo'yicha."""
    return {"price_history": crud_v5.list_price_history(
        db, product_id=product_id, price_type=price_type, limit=limit)}


# ================= KATEGORIYALAR (spec: /api/categories) =================
@router.get("/categories")
def api_categories(db: Session = Depends(get_db),
                   user: AuthUser = Depends(get_current_user)):
    """Spec: GET /api/categories — kategoriyalar ro'yxati."""
    return {"categories": crud_v5.list_categories(db)}


@router.post("/categories")
def api_create_category(data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: POST /api/categories — yangi kategoriya."""
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(400, "name kerak")
    return {"category": {"name": name}}


@router.put("/categories/{category_name}")
def api_rename_category(category_name: str, data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: PUT /api/categories/{id} — kategoriya nomini o'zgartirish."""
    new_name = str(data.get("new_name", "")).strip()
    if not new_name:
        raise HTTPException(400, "new_name kerak")
    n1 = db.query(models.Product).filter(models.Product.category == category_name).update(
        {models.Product.category: new_name}, synchronize_session=False)
    n2 = db.query(models.RawMaterial).filter(models.RawMaterial.category == category_name).update(
        {models.RawMaterial.category: new_name}, synchronize_session=False)
    db.commit()
    return {"success": True, "renamed": n1 + n2, "from": category_name, "to": new_name}


@router.delete("/categories/{category_name}")
def api_delete_category(category_name: str, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: DELETE /api/categories/{id} — kategoriyani o'chirish (mahsulotlar 'boshqa'ga)."""
    n1 = db.query(models.Product).filter(models.Product.category == category_name).update(
        {models.Product.category: "boshqa"}, synchronize_session=False)
    n2 = db.query(models.RawMaterial).filter(models.RawMaterial.category == category_name).update(
        {models.RawMaterial.category: "boshqa"}, synchronize_session=False)
    db.commit()
    return {"success": True, "moved_to": "boshqa", "products": n1, "materials": n2}


# ================= MIJOZLAR (spec: /api/customers) =================
@router.put("/customers/{customer_id}")
def api_update_customer(customer_id: int, data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_any_edit(["crm", "finance"]))):
    """Spec: PUT /api/customers/{id} — mijoz ma'lumotlarini tahrirlash."""
    allowed = {c.name for c in models.Customer.__table__.columns} - {
        "id", "total_debt", "total_purchases", "loyalty_points", "created_at", "updated_at"}
    payload = {k: v for k, v in data.items() if k in allowed}
    customer = crud.update_customer(db, customer_id, payload)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    return {"customer": crud.customer_to_dict(db, customer)}


@router.put("/customers/{customer_id}/credit")
def api_update_customer_credit(customer_id: int, data: dict, db: Session = Depends(get_db),
                               user: AuthUser = Depends(require_any_edit(["crm", "finance"]))):
    """Spec: PUT /api/customers/{id}/credit — kredit limitini o'zgartirish."""
    customer = crud.get_customer(db, customer_id)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    try:
        customer.credit_limit = float(data.get("credit_limit", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "credit_limit son bo'lishi kerak")
    db.commit()
    db.refresh(customer)
    return {"customer": crud.customer_to_dict(db, customer)}


@router.get("/customers/debtors")
def api_customer_debtors(db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_any_view_v5(["crm", "finance"]))):
    """Spec: GET /api/customers/debtors — qarzdor mijozlar."""
    customers = crud.list_customers(db, limit=1000)
    debtors = [c for c in customers if float(c.total_debt or 0) > 0]
    debtors.sort(key=lambda c: c.total_debt, reverse=True)
    return {"debtors": [crud.customer_to_dict(db, c) for c in debtors]}


@router.get("/customers/{customer_id}/orders")
def api_customer_orders(customer_id: int, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_role("crm"))):
    """Spec: GET /api/customers/{id}/orders — mijoz buyurtmalari."""
    if not crud.get_customer(db, customer_id):
        raise HTTPException(404, "Mijoz topilmadi")
    sales = db.query(models.Sale).filter(models.Sale.customer_id == customer_id).order_by(
        models.Sale.sale_date.desc()).limit(100).all()
    return {"orders": [{
        "id": s.id, "invoice_number": s.invoice_number,
        "product_id": s.product_id,
        "product_name": s.product.name if s.product else None,
        "quantity": s.quantity, "unit_price": s.unit_price,
        "total_amount": s.total_amount, "paid_amount": s.paid_amount,
        "discount_amount": s.discount_amount,
        "payment_method": s.payment_method, "is_credit": s.is_credit,
        "credit_status": s.credit_status,
        "sale_date": s.sale_date.isoformat() if s.sale_date else None,
        "due_date": s.due_date.isoformat() if s.due_date else None,
    } for s in sales]}


# ================= BUYURTMALAR / SOTUV (spec: /api/orders) =================
@router.get("/orders/sales")
def api_orders_sales(status: Optional[str] = None, limit: int = 100,
                     db: Session = Depends(get_db),
                     user: AuthUser = Depends(require_any_view_v5(["sales", "finance", "reports"]))):
    """Sotuv (buyurtma) ro'yxati — spec /api/orders (savdo fokusli)."""
    q = db.query(models.Sale)
    if status:
        q = q.filter(models.Sale.status == status)
    sales = q.order_by(desc(models.Sale.sale_date)).limit(limit).all()
    return {"orders": [{
        "id": s.id, "invoice_number": s.invoice_number,
        "product_id": s.product_id,
        "product_name": s.product.name if s.product else None,
        "quantity": s.quantity, "unit_price": s.unit_price,
        "total_amount": s.total_amount, "paid_amount": s.paid_amount,
        "discount_amount": s.discount_amount,
        "customer_id": s.customer_id, "customer_name": s.customer_name,
        "payment_method": s.payment_method, "is_credit": s.is_credit,
        "credit_status": s.credit_status, "sale_type": s.sale_type,
        "status": s.status, "user_name": s.user_name,
        "sale_date": s.sale_date.isoformat() if s.sale_date else None,
        "due_date": s.due_date.isoformat() if s.due_date else None,
        "notes": s.notes,
    } for s in sales]}


@router.post("/orders")
def api_create_order(data: dict, db: Session = Depends(get_db),
                     user: AuthUser = Depends(require_any_edit(["sales", "crm"]))):
    """Spec: POST /api/orders — yangi buyurtma (sotuv) yaratish.

    {
      product_id, quantity,
      unit_price? (berilmasa mahsulot narxi; quantity>=100 bo'lsa ulgurji),
      discount_amount?, sale_type? (retail|wholesale),
      payment_method? (cash|card|payme|click|credit|mixed),
      payments? [{method, amount}],
      customer_id? | customer_name?, customer_phone?,
      notes?
    }
    """
    product_id = data.get("product_id")
    quantity = float(data.get("quantity", 0))
    if not product_id or quantity <= 0:
        raise HTTPException(400, "product_id va quantity (0 dan katta) kerak")
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Mahsulot topilmadi")
    sale_type = str(data.get("sale_type", "retail")).strip()
    unit_price = data.get("unit_price")
    if unit_price is None:
        if sale_type == "wholesale" and quantity >= 100 and product.wholesale_price:
            unit_price = product.wholesale_price
        else:
            unit_price = product.selling_price or product.retail_price or 0
    unit_price = float(unit_price)
    total = round(quantity * unit_price, 2)
    discount = round(float(data.get("discount_amount", 0) or 0), 2)
    payments = data.get("payments")
    payment_method = str(data.get("payment_method", "cash")).strip()
    customer = None
    if data.get("customer_id"):
        customer = crud.get_customer(db, int(data["customer_id"]))
    if customer is None and data.get("customer_name"):
        phone = str(data.get("customer_phone", "")).strip() or None
        customer = crud.get_customer_by_phone(db, phone) if phone else None
        if customer is None and phone:
            try:
                customer = crud.create_customer(db, {
                    "name": str(data["customer_name"]).strip(), "phone": phone,
                })
            except Exception:
                customer = None
    try:
        sale = crud.create_sale_record(
            db, product_id=product_id, quantity=quantity,
            unit_price=unit_price, total_amount=total,
            discount_amount=discount,
            advance_amount=data.get("advance_amount"),
            payment_method=payment_method,
            payments=payments,
            customer=customer,
            customer_name=customer.name if customer else data.get("customer_name"),
            customer_phone=customer.phone if customer else data.get("customer_phone"),
            user_id=user.telegram_id or 0, user_name=user.full_name,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Xatolik: {e}")
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: sotuv {sale.invoice_number}", module="sales")
    return {"order": {
        "id": sale.id, "invoice_number": sale.invoice_number,
        "total_amount": sale.total_amount, "paid_amount": sale.paid_amount,
        "is_credit": sale.is_credit, "credit_status": sale.credit_status,
        "payment_method": sale.payment_method,
        "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
    }}


@router.put("/orders/{order_number}/status")
def api_update_order_status(order_number: str, data: dict, db: Session = Depends(get_db),
                            user: AuthUser = Depends(require_any_edit(["sales", "admin"]))):
    """Spec: PUT /api/orders/{id}/status — holatni o'zgartirish (bekor|completed)."""
    status = str(data.get("status", "")).strip()
    if status not in ("completed", "cancelled", "jarayonda"):
        raise HTTPException(400, "status: completed, cancelled yoki jarayonda")
    sale = db.query(models.Sale).filter(models.Sale.invoice_number == order_number).first()
    if not sale:
        raise HTTPException(404, "Buyurtma topilmadi")
    sale.status = status
    db.commit()
    return {"success": True, "invoice_number": order_number, "status": status}


@router.delete("/orders/{order_number}")
def api_cancel_order(order_number: str, db: Session = Depends(get_db),
                     user: AuthUser = Depends(require_any_edit(["sales", "admin"]))):
    """Spec: DELETE /api/orders/{id} — buyurtmani bekor qilish."""
    sale = db.query(models.Sale).filter(models.Sale.invoice_number == order_number).first()
    if not sale:
        raise HTTPException(404, "Buyurtma topilmadi")
    sale.status = "cancelled"
    db.commit()
    return {"success": True, "invoice_number": order_number, "status": "cancelled"}


@router.post("/orders/{order_number}/reserve")
def api_reserve_order(order_number: str, data: dict, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_any_edit(["sales", "stock_ops"]))):
    """Spec: POST /api/orders/{id}/reserve — buyurtma mahsulotini rezervatsiya qilish."""
    sale = db.query(models.Sale).filter(models.Sale.invoice_number == order_number).first()
    if not sale:
        raise HTTPException(404, "Buyurtma topilmadi")
    product_id = int(data.get("product_id", sale.product_id or 0))
    quantity = float(data.get("quantity", sale.quantity or 0))
    hours = float(data.get("hours", 24))
    result = crud.create_reservation(
        db, product_id, quantity, expires_in_hours=hours,
        customer_id=sale.customer_id, customer_name=sale.customer_name,
        created_by=user.full_name,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    reservation = result["reservation"]
    return {"reservation": {
        "id": reservation.id, "product_id": product_id,
        "quantity": quantity, "status": reservation.status,
        "expires_at": reservation.expires_at.isoformat() if reservation.expires_at else None,
    }}


@router.put("/orders/{order_number}/cancel-reserve")
def api_cancel_reserve_order(order_number: str, data: dict, db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_any_edit(["sales", "stock_ops"]))):
    """Spec: PUT /api/orders/{id}/cancel-reserve — rezervatsiyani bekor qilish."""
    sale = db.query(models.Sale).filter(models.Sale.invoice_number == order_number).first()
    if not sale:
        raise HTTPException(404, "Buyurtma topilmadi")
    reservation_id = data.get("reservation_id")
    if reservation_id:
        ok = crud.cancel_reservation(db, int(reservation_id))
    else:
        active = db.query(models.Reservation).filter(
            models.Reservation.product_id == sale.product_id,
            models.Reservation.status == models.ReservationStatus.ACTIVE,
        ).all()
        ok = False
        for r in active:
            crud.cancel_reservation(db, r.id)
            ok = True
    return {"success": ok}


# ================= TO'LOVLAR (spec: /api/payments) =================
@router.get("/payments")
def api_v5_payments(limit: int = 100, db: Session = Depends(get_db),
                    user: AuthUser = Depends(require_any_view_v5(["finance", "admin"]))):
    """Spec: GET /api/payments — to'lovlar ro'yxati."""
    payments = crud_v5.list_payments(db, limit=limit)
    return {"payments": [crud_v5.payment_to_dict(p) for p in payments]}


@router.post("/payments")
def api_v5_create_payment(data: dict, db: Session = Depends(get_db),
                          user: AuthUser = Depends(require_any_edit(["finance", "crm"]))):
    """Spec: POST /api/payments — to'lov qabul qilish.

    {sale_id?, customer_id?, amount, method} — sotuv to'lovi yoki qarz to'lovi.
    """
    amount = float(data.get("amount", 0))
    method = str(data.get("method", "cash")).strip()
    if amount <= 0:
        raise HTTPException(400, "amount 0 dan katta bo'lishi kerak")
    if method not in ("cash", "card", "payme", "click", "transfer"):
        raise HTTPException(400, "method: cash, card, payme, click yoki transfer")
    if data.get("sale_id"):
        sale = db.query(models.Sale).filter(models.Sale.id == int(data["sale_id"])).first()
        if not sale:
            raise HTTPException(404, "Sotuv topilmadi")
        remaining = float(sale.total_amount or 0) - float(sale.paid_amount or 0)
        if amount > remaining + 0.01:
            raise HTTPException(400, "To'lov qolgan qarzdan katta")
        sale.paid_amount = float(sale.paid_amount or 0) + amount
        if sale.customer_id:
            cust = crud.get_customer(db, sale.customer_id)
            if cust:
                cust.total_debt = max(float(cust.total_debt or 0) - amount, 0)
        if float(sale.paid_amount) >= float(sale.total_amount) - 0.01:
            sale.credit_status = "toliq_tolangan"
        payment = models.Payment(
            sale_id=sale.id, customer_id=sale.customer_id,
            amount=amount, method=method, payment_type="sale",
            note=data.get("note"), created_by=user.full_name,
        )
        db.add(payment)
        db.commit()
        return {"payment": crud_v5.payment_to_dict(payment)}
    customer_id = data.get("customer_id")
    if customer_id:
        result = crud.pay_customer_debt(
            db, int(customer_id), amount, method=method,
            note=data.get("note"), created_by=user.full_name,
        )
        if result is None:
            raise HTTPException(404, "Mijoz topilmadi")
        return {"success": True, **result}
    raise HTTPException(400, "sale_id yoki customer_id kerak")


@router.get("/payments/daily")
def api_v5_payments_daily(day: Optional[str] = None, db: Session = Depends(get_db),
                          user: AuthUser = Depends(require_any_view_v5(["finance", "admin"]))):
    """Spec: GET /api/payments/daily — kunlik to'lov hisoboti."""
    target = _parse_day(day) if day else date.today()
    return crud_v5.get_daily_payments(db, target)


# ================= OMBOR / INVENTORY (spec: /api/inventory) =================
@router.get("/inventory")
def api_inventory(db: Session = Depends(get_db),
                  user: AuthUser = Depends(require_role("warehouse"))):
    """Spec: GET /api/inventory — barcha omborlar qoldig'i."""
    products = db.query(models.Product).filter(models.Product.is_active.is_(True)).all()
    materials = db.query(models.RawMaterial).all()
    return {
        "products": [{
            **product_to_dict(p),
            "available_qty": crud.get_available_product_qty(db, p.id),
        } for p in products],
        "raw_materials": [{
            "id": m.id, "name": m.name, "unit": m.unit,
            "current_stock": m.current_stock, "min_stock": m.min_stock,
            "max_stock": m.max_stock, "price_per_unit": m.price_per_unit,
            "category": m.category, "warehouse": m.warehouse, "sector": m.sector,
            "supplier": m.supplier,
            "value": round(float(m.current_stock or 0) * float(m.price_per_unit or 0), 0),
        } for m in materials],
    }


@router.put("/inventory/adjust")
def api_inventory_adjust(data: dict, db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_role("warehouse", edit=True))):
    """Spec: PUT /api/inventory/adjust — qoldiqni tuzatish (omborchi)."""
    item_type = str(data.get("item_type", "product")).strip()
    item_id = int(data.get("item_id", 0))
    delta = float(data.get("delta", 0))
    if delta == 0:
        raise HTTPException(400, "delta 0 dan farqli bo'lishi kerak")
    if item_type == "raw":
        mat = db.query(models.RawMaterial).filter(models.RawMaterial.id == item_id).first()
        if not mat:
            raise HTTPException(404, "Xom ashyo topilmadi")
        new_stock = float(mat.current_stock or 0) + delta
        if new_stock < 0:
            raise HTTPException(400, "Qoldiq manfiy bo'lishi mumkin emas")
        mat.current_stock = new_stock
        tr = models.WarehouseTransaction(
            raw_material_id=item_id, quantity=delta,
            transaction_type=models.TransactionType.INVENTORY,
            user_id=user.telegram_id or 0, user_name=user.full_name,
            document_number=f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            notes=data.get("reason") or "Qoldiq tuzatish",
        )
    else:
        product = db.query(models.Product).filter(models.Product.id == item_id).first()
        if not product:
            raise HTTPException(404, "Mahsulot topilmadi")
        new_qty = crud.get_available_product_qty(db, item_id) + delta
        if new_qty < 0:
            raise HTTPException(400, "Qoldiq manfiy bo'lishi mumkin emas")
        tr = models.WarehouseTransaction(
            product_id=item_id, quantity=delta,
            transaction_type=models.TransactionType.INVENTORY,
            user_id=user.telegram_id or 0, user_name=user.full_name,
            document_number=f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            notes=data.get("reason") or "Qoldiq tuzatish",
        )
    db.add(tr)
    db.commit()
    return {"success": True, "item_type": item_type, "item_id": item_id, "delta": delta}


@router.get("/inventory/history")
def api_inventory_history(item_type: Optional[str] = None, item_id: Optional[int] = None,
                          limit: int = 100, db: Session = Depends(get_db),
                          user: AuthUser = Depends(require_role("warehouse"))):
    """Spec: GET /api/inventory/history — tovar harakat tarixi."""
    return {"history": crud_v5.get_inventory_history(
        db, item_type=item_type, item_id=item_id, limit=limit)}


@router.get("/inventory/{product_id}")
def api_inventory_product(product_id: int, db: Session = Depends(get_db),
                          user: AuthUser = Depends(get_current_user)):
    """Spec: GET /api/inventory/{product_id} — mahsulot qoldig'i."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Mahsulot topilmadi")
    return {
        "product": product_to_dict(product),
        "available_qty": crud.get_available_product_qty(db, product_id),
    }


# ================= YETKAZIB BERISH: MULOJOT IMZOSI (spec: signature) =================
@router.post("/deliveries/{delivery_id}/signature")
def api_delivery_signature(delivery_id: int, data: dict, db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_any_edit(["delivery", "admin"]))):
    """Spec: POST /api/deliveries/{id}/signature — mijoz imzosi (PIN/barmoq izi)."""
    delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(404, "Yetkazib berish topilmadi")
    signature_name = str(data.get("signature_name") or data.get("name") or "").strip()
    if not signature_name:
        raise HTTPException(400, "signature_name (imzo qoldiruvchi) kerak")
    signature_type = str(data.get("signature_type", "pin")).strip()
    if signature_type not in ("pin", "fingerprint"):
        raise HTTPException(400, "signature_type: pin yoki fingerprint")
    delivery.signature_name = signature_name
    delivery.signature_type = signature_type
    delivery.signature_at = datetime.utcnow()
    db.commit()
    return {"success": True, "delivery_id": delivery_id,
            "signature_name": signature_name, "signature_at": delivery.signature_at.isoformat()}


# ================= HISOBOTLAR (spec: /api/reports) =================
@router.get("/reports/daily")
def api_report_daily(day: Optional[str] = None, db: Session = Depends(get_db),
                     user: AuthUser = Depends(require_role("reports"))):
    """Spec: GET /api/reports/daily — kunlik hisobot."""
    target = _parse_day(day) if day else date.today()
    start = datetime.combine(target, datetime.min.time())
    end = datetime.combine(target, datetime.max.time())
    return {"period": "daily", "date": target.isoformat(),
            **_report_stats(db, start, end)}


@router.get("/reports/weekly")
def api_report_weekly(db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_role("reports"))):
    start, end = _period_range(7)
    return {"period": "weekly", "days": 7, **_report_stats(db, start, end)}


@router.get("/reports/monthly")
def api_report_monthly(days: int = 30, db: Session = Depends(get_db),
                       user: AuthUser = Depends(require_role("reports"))):
    start, end = _period_range(days)
    return {"period": "monthly", "days": days, **_report_stats(db, start, end)}


@router.get("/reports/yearly")
def api_report_yearly(db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_role("reports"))):
    end = datetime.utcnow()
    start = datetime(end.year, 1, 1)
    stats = _report_stats(db, start, end)
    # Oylar kesimida savdo (yillik daromad grafigi uchun)
    rows = db.query(
        func.strftime("%Y-%m", models.Sale.sale_date).label("month"),
        func.sum(models.Sale.total_amount).label("total"),
    ).filter(models.Sale.sale_date >= start).group_by("month").all()
    stats["monthly"] = [{"month": r.month, "total": round(float(r.total or 0), 0)} for r in rows]
    return {"period": "yearly", "year": end.year, **stats}


@router.get("/reports/profit-loss")
def api_report_profit_loss(start: Optional[str] = None, end: Optional[str] = None,
                           db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_role("reports"))):
    """Spec: GET /api/reports/profit-loss — Foyda/Zarar (alias: /api/finance/pl)."""
    start_date = _parse_day(start) if start else (date.today() - timedelta(days=30))
    end_date = _parse_day(end) if end else date.today()
    return crud.get_pl_report(db, start_date, end_date)


@router.get("/reports/debt")
def api_report_debt(db: Session = Depends(get_db),
                    user: AuthUser = Depends(require_role("reports"))):
    """Spec: GET /api/reports/debt — qarz hisoboti (alias: /api/finance/debts)."""
    return crud.get_customer_debts_report(db)


@router.get("/reports/top-customers")
def api_report_top_customers(days: Optional[int] = None, limit: int = 20,
                             db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("reports"))):
    """Spec: GET /api/reports/top-customers — eng yaxshi mijozlar TOP-20."""
    return {"customers": crud_v5.get_top_customers(db, limit=limit, days=days)}


@router.get("/reports/sales-by-category")
def api_report_sales_by_category(days: int = 30, db: Session = Depends(get_db),
                                 user: AuthUser = Depends(require_role("reports"))):
    """Spec: GET /api/reports/sales-by-category — kategoriya bo'yicha savdo."""
    return {"categories": crud_v5.get_sales_by_category(db, days=days)}


@router.post("/reports/export")
def api_report_export(data: dict, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_role("reports"))):
    """Spec: POST /api/reports/export — Excel/CSV eksport.

    {report: "daily"|"weekly"|"monthly"|"yearly"|"sales"|"payments"|"inventory",
     format: "csv"|"json"} — CSV qaytaradi (Excel'da ochiladi).
    """
    report = str(data.get("report", "daily")).strip()
    fmt = str(data.get("format", "csv")).strip()
    days = int(data.get("days", 30) or 30)
    start, end = _period_range(days)
    if report == "sales":
        sales = db.query(models.Sale).filter(
            models.Sale.sale_date >= start, models.Sale.sale_date <= end
        ).order_by(models.Sale.sale_date.desc()).all()
        headers = ["invoice_number", "product_name", "quantity", "unit_price",
                   "total_amount", "paid_amount", "discount_amount", "customer_name",
                   "payment_method", "is_credit", "sale_date"]
        rows = [[
            s.invoice_number, s.product.name if s.product else None,
            s.quantity, s.unit_price, s.total_amount, s.paid_amount,
            s.discount_amount, s.customer_name, s.payment_method,
            s.is_credit, s.sale_date.isoformat() if s.sale_date else None,
        ] for s in sales]
    elif report == "payments":
        payments = crud_v5.list_payments(db, start_date=start, end_date=end, limit=1000)
        headers = ["id", "sale_id", "amount", "method", "payment_type",
                   "created_by", "created_at"]
        rows = [[p.id, p.sale_id, p.amount, p.method, p.payment_type,
                 p.created_by, p.created_at.isoformat() if p.created_at else None]
                for p in payments]
    elif report == "inventory":
        products = db.query(models.Product).filter(models.Product.is_active.is_(True)).all()
        headers = ["id", "name", "category", "unit", "selling_price",
                   "wholesale_price", "available_qty", "warehouse", "sector"]
        rows = [[p.id, p.name, p.category, p.unit, p.selling_price,
                 p.wholesale_price, crud.get_available_product_qty(db, p.id),
                 p.warehouse, p.sector] for p in products]
    elif report == "customers":
        customers = crud.list_customers(db, limit=1000)
        headers = ["id", "name", "phone", "total_debt", "total_purchases",
                   "credit_limit", "loyalty_points", "tier"]
        rows = [[c.id, c.name, c.phone, c.total_debt, c.total_purchases,
                 c.credit_limit, c.loyalty_points,
                 crud.calculate_customer_tier(db, c)] for c in customers]
    else:
        stats = _report_stats(db, start, end)
        headers = ["metric", "value"]
        rows = [[k, v] for k, v in stats.items()
                if not isinstance(v, (dict, list))]
    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    csv_text = buf.getvalue()
    if fmt == "json":
        return {"success": True, "report": report, "rows": rows, "headers": headers}
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{report}.csv"'},
    )


# ================= YETKAZIB BERUVCHILAR (spec: /api/suppliers) =================
@router.put("/suppliers/{supplier_id}")
def api_update_supplier(supplier_id: int, data: dict, db: Session = Depends(get_db),
                        user: AuthUser = Depends(require_any_edit(["supplier", "admin"]))):
    """Spec: PUT /api/suppliers/{id} — yetkazib beruvchini tahrirlash."""
    allowed = {c.name for c in models.Supplier.__table__.columns} - {
        "id", "rating", "on_time_count", "late_count", "created_at", "updated_at"}
    payload = {k: v for k, v in data.items() if k in allowed}
    supplier = crud.update_supplier(db, supplier_id, payload)
    if not supplier:
        raise HTTPException(404, "Yetkazib beruvchi topilmadi")
    return {"supplier": crud.supplier_to_dict(supplier)}


@router.get("/suppliers/{supplier_id}/purchases")
def api_supplier_purchases(supplier_id: int, limit: int = 100,
                           db: Session = Depends(get_db),
                           user: AuthUser = Depends(require_any_view_v5(["supplier", "admin"]))):
    """Spec: GET /api/suppliers/{id}/purchases — xarid tarixi."""
    if not crud.get_supplier(db, supplier_id):
        raise HTTPException(404, "Yetkazib beruvchi topilmadi")
    deliveries = db.query(models.SupplierDelivery).filter(
        models.SupplierDelivery.supplier_id == supplier_id
    ).order_by(desc(models.SupplierDelivery.created_at)).limit(limit).all()
    return {"purchases": [{
        "id": d.id, "act_number": d.act_number,
        "raw_material_id": d.raw_material_id,
        "raw_material_name": d.raw_material.name if d.raw_material else None,
        "quantity_ordered": d.quantity_ordered,
        "quantity_received": d.quantity_received,
        "quality_status": d.quality_status,
        "price_per_unit": d.price_per_unit,
        "deficiency_amount": d.deficiency_amount,
        "notes": d.notes, "created_by": d.created_by,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in deliveries]}


# ================= ISHLAB CHIQARISH (spec: /api/production) =================
@router.get("/production")
def api_v5_production(status: Optional[str] = None, db: Session = Depends(get_db),
                      user: AuthUser = Depends(require_any_view_v5(["production", "admin"]))):
    """Spec: GET /api/production — ishlab chiqarish buyurtmalari."""
    orders = crud_v5.list_production_orders(db, status=status)
    return {"production_orders": [crud_v5.production_order_to_dict(db, o) for o in orders]}


@router.post("/production")
def api_v5_create_production(data: dict, db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: POST /api/production — ishlab chiqarish buyurtmasi (Direktor)."""
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    if not product_id or not quantity:
        raise HTTPException(400, "product_id va quantity kerak")
    product = db.query(models.Product).filter(models.Product.id == int(product_id)).first()
    if not product:
        raise HTTPException(404, "Mahsulot topilmadi")
    payload = {
        "product_id": int(product_id),
        "quantity": int(quantity),
        "priority": int(data.get("priority", 1) or 1),
        "responsible_id": data.get("responsible_id"),
        "notes": data.get("notes"),
        "planned_start": datetime.utcnow(),
    }
    if data.get("planned_end"):
        try:
            payload["planned_end"] = datetime.fromisoformat(str(data["planned_end"]))
        except ValueError:
            raise HTTPException(400, "planned_end ISO formatda bo'lishi kerak")
    try:
        order = crud.create_production_order(db, payload)
    except Exception as e:
        raise HTTPException(400, str(e))
    crud.create_system_log(db, user_id=user.telegram_id, user_name=user.full_name,
                           action=f"API: ishlab chiqarish buyurtmasi {order.order_number}",
                           module="production")
    return {"production_order": crud_v5.production_order_to_dict(db, order)}


@router.put("/production/{order_id}/status")
def api_v5_production_status(order_id: int, data: dict, db: Session = Depends(get_db),
                             user: AuthUser = Depends(require_any_edit(["production", "admin"]))):
    """Spec: PUT /api/production/{id}/status — holatni o'zgartirish."""
    status = str(data.get("status", "")).strip()
    valid = ("kutilmoqda", "jarayonda", "tayyor", "bekor", "bekor_qilingan")
    if status not in valid:
        raise HTTPException(400, f"status: {', '.join(valid)}")
    order = crud_v5.update_production_order_status(
        db, order_id, status,
        actual_start=datetime.utcnow() if status == "jarayonda" else None,
        actual_end=datetime.utcnow() if status == "tayyor" else None,
    )
    if not order:
        raise HTTPException(404, "Buyurtma topilmadi")
    return {"success": True, "status": status}


# ================= OMBORLAR (spec: /api/warehouses) =================
@router.get("/warehouses")
def api_warehouses(db: Session = Depends(get_db),
                   user: AuthUser = Depends(require_any_view_v5(["warehouse", "admin"]))):
    """Spec: GET /api/warehouses — omborlar ro'yxati."""
    warehouses = crud_v5.list_warehouses(db, active_only=False)
    return {"warehouses": [crud_v5.warehouse_to_dict(w) for w in warehouses]}


@router.post("/warehouses")
def api_create_warehouse(data: dict, db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_role("admin", edit=True))):
    """Spec: POST /api/warehouses — yangi ombor qo'shish (Direktor)."""
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(400, "name kerak")
    if db.query(models.Warehouse).filter(models.Warehouse.name == name).first():
        raise HTTPException(400, "Bunday ombor mavjud")
    try:
        wh = crud_v5.create_warehouse(db, data)
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"warehouse": crud_v5.warehouse_to_dict(wh)}


@router.put("/warehouses/{warehouse_id}")
def api_update_warehouse(warehouse_id: int, data: dict, db: Session = Depends(get_db),
                         user: AuthUser = Depends(require_any_edit(["warehouse", "admin"]))):
    """Spec: PUT /api/warehouses/{id} — omborni tahrirlash."""
    wh = crud_v5.update_warehouse(db, warehouse_id, data)
    if not wh:
        raise HTTPException(404, "Ombor topilmadi")
    return {"warehouse": crud_v5.warehouse_to_dict(wh)}

