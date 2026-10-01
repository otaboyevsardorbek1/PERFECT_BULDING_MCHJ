"""
Ommaviy web-do'kon API (catalog -> savat -> checkout) — auth talab qilmaydi

- GET  /api/shop/catalog        Katalog (faol mahsulotlar, zaxiradagi miqdor)
- GET  /api/shop/categories     Kategoriyalar
- POST /api/shop/orders         Buyurtma yaratish (naqd / Click / Payme)
- GET  /api/shop/orders/{number}?phone=  Buyurtma holatini tekshirish
- POST /api/shop/orders/{number}/cancel  Kutilayotgan buyurtmani bekor qilish

Buyurtma oqimi:
- cash  -> darhol yakunlangan sotuv (Sale) sifatida yoziladi
- click/payme -> PaymentInvoice ochiladi, to'lov tasdiqlanganda Sale yoziladi
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import crud, models
from database.session import get_db

router = APIRouter(prefix="/api/shop", tags=["shop"])


def _catalog_product(db: Session, p: models.Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "unit": p.unit,
        "price": p.selling_price or 0,
        "description": p.description,
        "available": crud.get_available_product_qty(db, p.id),
    }


@router.get("/catalog")
def shop_catalog(category: Optional[str] = None, q: Optional[str] = None,
                 limit: int = 100, db: Session = Depends(get_db)):
    """Do'kon katalogi — faqat faol mahsulotlar va sotuvga tayyor miqdor"""
    query = db.query(models.Product).filter(models.Product.is_active == True)
    if category:
        query = query.filter(models.Product.category == category)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(models.Product.name.ilike(like))
    products = query.order_by(models.Product.name).limit(max(limit, 1)).all()
    return {"products": [_catalog_product(db, p) for p in products],
            "count": len(products)}


@router.get("/categories")
def shop_categories(db: Session = Depends(get_db)):
    """Faol mahsulotlar kategoriyalari (mahsulot soni bilan)"""
    rows = db.query(
        models.Product.category,
        models.Product.category.label("name"),
    ).filter(
        models.Product.is_active == True,
        models.Product.category.isnot(None),
    ).all()
    counts: dict = {}
    for (cat, _name) in rows:
        counts[cat] = counts.get(cat, 0) + 1
    return {"categories": [
        {"name": name, "products": count} for name, count in sorted(counts.items())
    ]}


@router.post("/orders")
def shop_create_order(data: dict, db: Session = Depends(get_db)):
    """Checkout: buyurtma yaratish.

    Javob:
      - cash:   {order: ..., status: "yakunlangan"}
      - onlayn: {order: ..., invoice_id: ..., payment_link: "..."}
    """
    try:
        method = str(data.get("method", "cash")).lower()
        cash_amount = data.get("cash_amount")
        online_gateway = data.get("online_gateway")
        order = crud.create_shop_order(
            db,
            name=str(data.get("name", "")),
            phone=str(data.get("phone", "")),
            address=data.get("address"),
            comment=data.get("comment"),
            method=method,
            items=data.get("items") or [],
            cash_amount=cash_amount,
            online_gateway=data.get("online_gateway"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Onlayn qismi bo'lgan buyurtmalar (to'liq yoki aralash): schyot ochiladi
    needs_payment = method in ("click", "payme") or (
        method == "mixed" and (order.online_amount or 0) > 0
    )
    if needs_payment:
        try:
            from dashboard.payments import build_payment_links, create_payment_invoice
            gateway = order.online_gateway or method
            amount = order.online_amount if method == "mixed" else order.total_amount
            invoice = create_payment_invoice(
                db,
                gateway=gateway,
                amount=amount,
                customer_id=order.customer_id,
                customer_name=order.customer_name,
                note=order.order_number,
            )
            invoice.shop_order_id = order.id
            order.invoice_id = invoice.invoice_id
            db.commit()
            db.refresh(order)
            db.refresh(invoice)
            links = build_payment_links(invoice)
            link = links.get(gateway)
            if not link:
                raise HTTPException(
                    503,
                    f"{gateway.upper()} to'lov sozlanmagan (kalit yo'q). "
                    "Iltimos naqd usulini tanlang yoki boshqa to'lovni sinang.",
                )
            return {
                "order": crud.shop_order_to_dict(order),
                "invoice_id": invoice.invoice_id,
                "payment_link": link,
                "links": links,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"To'lov schyoti ochilmadi: {e}")

    return {"order": crud.shop_order_to_dict(order), "status": "yakunlangan"}


@router.get("/orders/{order_number}")
def shop_order_status(order_number: str, phone: str = "",
                      db: Session = Depends(get_db)):
    """Buyurtma holati (mijoz o'z raqami bilan tekshiradi)"""
    order = crud.get_shop_order_by_number(db, order_number)
    if not order:
        raise HTTPException(404, "Buyurtma topilmadi")
    caller = crud._shop_phone(phone)
    if not caller or caller != (order.customer_phone or ""):
        raise HTTPException(403, "Buyurtma holatini ko'rish uchun telefon raqami mos emas")
    return {"order": crud.shop_order_to_dict(order)}


@router.post("/orders/{order_number}/cancel")
def shop_cancel_order(order_number: str, data: dict = None,
                      db: Session = Depends(get_db)):
    """To'lanmagan buyurtmani bekor qilish (telefon tasdiqlashi bilan)"""
    order = crud.get_shop_order_by_number(db, order_number)
    if not order:
        raise HTTPException(404, "Buyurtma topilmadi")
    caller = crud._shop_phone((data or {}).get("phone", ""))
    if not caller or caller != (order.customer_phone or ""):
        raise HTTPException(403, "Bekor qilish uchun telefon raqami mos emas")
    try:
        crud.cancel_shop_order(db, order.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"order": crud.shop_order_to_dict(order)}
