"""
💳 Onlayn to'lovlar — Click (SHOP API) va Payme (Merchant API)

Mijoz Click/Payme ilovasida to'laganda, to'lov tizimi bizning serverimizga
webhook yuboradi. Bu modul:
  - Click:  POST /api/payments/click   (prepare + complete, MD5 imzo)
  - Payme:  POST /api/payments/payme   (JSON-RPC 2.0, Basic auth)

Sozlash (.env):
  CLICK_MERCHANT_ID / CLICK_SERVICE_ID / CLICK_SECRET_KEY
  PAYME_MERCHANT_ID / PAYME_KEY
  PAYMENT_RETURN_URL  (mijoz to'lovdan keyin qaytadigan sahifa)

Webhook URL'lari (Click kabinetida va Payme kabinetida shu manzillar beriladi):
  https://<domen>/api/payments/click
  https://<domen>/api/payments/payme
"""

import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import (
    CLICK_MERCHANT_ID, CLICK_SERVICE_ID, CLICK_SECRET_KEY,
    PAYME_MERCHANT_ID, PAYME_KEY, PAYMENT_RETURN_URL,
)
from database import crud, models
from database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ============================================================
# UMUMIY YORDAMCHILAR
# ============================================================

def _new_invoice_id() -> str:
    """Yagona schyot-faktura raqami (Click merchant_trans_id / Payme order_id)"""
    return f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3).upper()}"


def create_payment_invoice(db: Session, *, gateway: str, amount: float,
                           customer_id: int = None, customer_name: str = None,
                           note: str = None) -> models.PaymentInvoice:
    """Yangi onlayn to'lov schyot-fakturasi yaratadi (pending status)"""
    if gateway not in ("click", "payme"):
        raise ValueError("gateway 'click' yoki 'payme' bo'lishi kerak")
    if not amount or amount <= 0:
        raise ValueError("Summa 0 dan katta bo'lishi kerak")
    invoice = models.PaymentInvoice(
        invoice_id=_new_invoice_id(),
        gateway=gateway,
        amount=float(amount),
        status="pending",
        customer_id=customer_id,
        customer_name=customer_name,
        note=note,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def build_payment_links(invoice: models.PaymentInvoice) -> dict:
    """Mijozga yuboriladigan to'lov havolalari (Click va Payme)"""
    links = {}
    ret = PAYMENT_RETURN_URL or ""
    if CLICK_MERCHANT_ID and CLICK_SERVICE_ID:
        click_url = (
            f"https://my.click.uz/services/pay?service_id={CLICK_SERVICE_ID}"
            f"&merchant_id={CLICK_MERCHANT_ID}&amount={int(round(invoice.amount))}"
            f"&transaction_param={invoice.invoice_id}"
        )
        if ret:
            click_url += f"&return_url={ret}"
        links["click"] = click_url
    if PAYME_MERCHANT_ID:
        # https://checkout.paycom.uz/<base64("m={id};ac.order_id={inv};a={tiyin};c={return}")>
        raw = (
            f"m={PAYME_MERCHANT_ID};ac.order_id={invoice.invoice_id};"
            f"a={int(round(invoice.amount * 100))};c={ret}"
        )
        b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        links["payme"] = f"https://checkout.paycom.uz/{b64}"
    return links


def invoice_to_dict(inv: models.PaymentInvoice) -> dict:
    return {
        "id": inv.id,
        "invoice_id": inv.invoice_id,
        "gateway": inv.gateway,
        "amount": inv.amount,
        "status": inv.status,
        "customer_id": inv.customer_id,
        "customer_name": inv.customer_name,
        "note": inv.note,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    }


def _confirm_payment(db: Session, invoice: models.PaymentInvoice, *, gateway: str):
    """To'lov tasdiqlanganda: Payment yozuvi + mijoz qarzini yopish
    yoki web-do'kon buyurtmasini yakunlash (shop_order_id bo'lsa)."""
    if invoice.status == "paid":
        return  # ikki marta tasdiqlashni oldini olish (idempotent)
    invoice.status = "paid"
    invoice.paid_at = datetime.utcnow()
    db.commit()

    method = "payme" if gateway == "payme" else "click"

    # Web-do'kon buyurtmasi: to'lov tasdiqlanganda Sale yoziladi, buyurtma yakunlanadi
    if invoice.shop_order_id:
        try:
            crud.finalize_shop_order_payment(
                db, invoice.shop_order_id, method=method, invoice_id=invoice.invoice_id
            )
            try:
                crud.create_system_log(
                    db, user_id=0, user_name="PaymentGateway",
                    action=f"Do'kon buyurtmasi to'landi: {invoice.invoice_id} "
                           f"{invoice.amount:,.0f} so'm ({method})",
                    module="payments",
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Do'kon buyurtmasini yakunlashda xatolik: {e}")
            db.rollback()
        return

    try:
        if invoice.customer_id:
            crud.pay_customer_debt(
                db, invoice.customer_id, invoice.amount,
                method=method,
                note=f"Onlayn to'lov #{invoice.invoice_id}",
                created_by="PaymentGateway",
            )
        else:
            db.add(models.Payment(
                amount=invoice.amount, method=method,
                payment_type="debt",
                note=f"Onlayn to'lov #{invoice.invoice_id}",
                created_by="PaymentGateway",
            ))
            db.commit()
        try:
            crud.create_system_log(
                db, user_id=0, user_name="PaymentGateway",
                action=f"Onlayn to'lov qabul qilindi: {invoice.invoice_id} "
                       f"{invoice.amount:,.0f} so'm ({method})",
                module="payments",
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"To'lovni hisobga olishda xatolik: {e}")
        db.rollback()


# ============================================================
# CLICK SHOP API
# ============================================================

# Click xatolik kodlari (rasmiy jadval — o'zgartirilmaydi)
CLICK_ERR = {
    "success": 0,
    "sign_check_failed": -1,
    "incorrect_amount": -2,
    "action_not_found": -3,
    "already_paid": -4,
    "user_not_found": -5,
    "transaction_not_found": -6,
    "failed_to_update": -7,
    "error_in_request": -8,
    "transaction_cancelled": -9,
}


def _click_sign(params: dict, *, prepare: bool) -> str:
    """Click imzosini hisoblash.

    Prepare (action=0): md5(click_trans_id + service_id + SECRET + merchant_trans_id
                            + amount + action + sign_time)
    Complete (action=1): yuqoridagiga merchant_prepare_id ham qo'shiladi:
                            ... + merchant_trans_id + merchant_prepare_id + amount ...
    Barcha qiymatlar qator sifatida birlashtiriladi (separator yo'q).
    """
    parts = [
        str(params.get("click_trans_id", "")),
        str(params.get("service_id", "")),
        str(CLICK_SECRET_KEY),
        str(params.get("merchant_trans_id", "")),
    ]
    if not prepare:
        parts.append(str(params.get("merchant_prepare_id", "")))
    parts += [
        str(params.get("amount", "")),
        str(params.get("action", "")),
        str(params.get("sign_time", "")),
    ]
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest()


def _click_response(click_trans_id, merchant_trans_id, error: int, error_note: str,
                    prepare_id=None, confirm_id=None) -> dict:
    resp = {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "error": error,
        "error_note": error_note,
    }
    if confirm_id is not None:
        resp["merchant_confirm_id"] = confirm_id
    else:
        resp["merchant_prepare_id"] = prepare_id or 0
    return resp


@router.post("/click")
async def click_webhook(request: Request, db: Session = Depends(get_db)):
    """Click SHOP API webhook — prepare (action=0) va complete (action=1).

    Click POST so'rovni form-encoded (JSON EMAS!) yuboradi.
    """
    try:
        form = await request.form()
        params = {k: str(v) for k, v in form.items()}
    except Exception:
        return JSONResponse(content={"error": "Invalid form data"}, status_code=400)

    click_trans_id = params.get("click_trans_id", "")
    service_id = params.get("service_id", "")
    merchant_trans_id = params.get("merchant_trans_id", "")
    action = params.get("action", "")

    def _err(code: str, prepare_id=None, confirm_id=None):
        return _click_response(click_trans_id, merchant_trans_id,
                               CLICK_ERR[code], code.upper(),
                               prepare_id=prepare_id, confirm_id=confirm_id)

    # 1) Service ID tekshirish
    if str(service_id) != str(CLICK_SERVICE_ID):
        return _err("error_in_request")

    # 2) Schyot-faktura topish
    invoice = db.query(models.PaymentInvoice).filter(
        models.PaymentInvoice.invoice_id == merchant_trans_id
    ).first()
    if not invoice:
        return _err("user_not_found")

    try:
        action_num = int(action)
        amount_num = int(round(float(params.get("amount", 0))))
    except (TypeError, ValueError):
        return _err("error_in_request")

    if int(round(invoice.amount)) != amount_num:
        return _err("incorrect_amount", prepare_id=invoice.merchant_prepare_id)

    # 3) Imzoni tekshirish
    if params.get("sign_string", "") != _click_sign(params, prepare=(action_num == 0)):
        return _err("sign_check_failed", prepare_id=invoice.merchant_prepare_id)

    if action_num == 0:
        # ---- PREPARE: Click mijozdan to'lovni so'rayapti ----
        if invoice.status == "paid":
            return _err("already_paid", prepare_id=invoice.merchant_prepare_id)

        # merchant_prepare_id: 32-bit int, qayta chaqiruvda BIR XIL qaytadi
        if not invoice.merchant_prepare_id:
            invoice.merchant_prepare_id = str(
                int(datetime.now().timestamp() * 1000) % 2147483647
            )
        invoice.click_trans_id = click_trans_id
        invoice.click_paydoc_id = params.get("click_paydoc_id", "")
        db.commit()
        return _click_response(click_trans_id, merchant_trans_id, 0, "Success",
                               prepare_id=invoice.merchant_prepare_id)

    elif action_num == 1:
        # ---- COMPLETE: to'lov amalga oshdi (yoki bank rad etdi) ----
        # error < 0 bo'lsa to'lov muvaffaqiyatsiz
        try:
            click_error = int(params.get("error", "0"))
        except (TypeError, ValueError):
            click_error = 0

        if click_error < 0:
            if invoice.status == "pending":
                invoice.status = "cancelled"
                db.commit()
            return _err("transaction_cancelled", prepare_id=invoice.merchant_prepare_id)

        if invoice.status == "paid":
            # Allaqachon to'langan — -4 qaytaramiz (0 emas), Click qayta urinmaydi
            return _err("already_paid", prepare_id=invoice.merchant_prepare_id)

        # merchant_prepare_id mosligi (Click complete'da yuboradi)
        prep = params.get("merchant_prepare_id", "")
        if invoice.merchant_prepare_id and prep and prep != invoice.merchant_prepare_id:
            return _err("transaction_not_found", prepare_id=prep)

        if not invoice.merchant_prepare_id:
            invoice.merchant_prepare_id = prep or str(
                int(datetime.now().timestamp() * 1000) % 2147483647
            )
        invoice.click_trans_id = click_trans_id
        invoice.click_paydoc_id = params.get("click_paydoc_id", "")
        db.commit()

        _confirm_payment(db, invoice, gateway="click")
        invoice = db.query(models.PaymentInvoice).filter(
            models.PaymentInvoice.id == invoice.id
        ).first()
        confirm_id = invoice.merchant_confirm_id or str(
            int(datetime.now().timestamp() * 1000) % 2147483647
        )
        invoice.merchant_confirm_id = confirm_id
        db.commit()
        return _click_response(click_trans_id, merchant_trans_id, 0, "Success",
                               confirm_id=confirm_id)

    return _err("action_not_found", prepare_id=invoice.merchant_prepare_id)


# ============================================================
# PAYME MERCHANT API (JSON-RPC 2.0)
# ============================================================

PAYME_STATE_CREATED = 1
PAYME_STATE_PERFORMED = 2
PAYME_STATE_CANCELLED = -1
PAYME_STATE_CANCELLED_TIMEOUT = -2


def _payme_rpc(rpc_id, result=None, error=None) -> JSONResponse:
    body = {"jsonrpc": "2.0", "id": rpc_id}
    if error is not None:
        body["error"] = error
    else:
        body["result"] = result
    return JSONResponse(content=body)


def _payme_error(rpc_id, code: int, message: str, data=None) -> JSONResponse:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return _payme_rpc(rpc_id, error=err)


def _payme_authorized(request: Request) -> bool:
    """X-Authorization: Basic base64(login:password) — parol PAYME_KEY'ga teng bo'lishi kerak"""
    auth = request.headers.get("x-authorization", "") or request.headers.get("authorization", "")
    if not auth.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:].strip()).decode("utf-8")
        login, _, key = decoded.partition(":")
    except Exception:
        return False
    if key != PAYME_KEY:
        return False
    if login and PAYME_MERCHANT_ID and login != PAYME_MERCHANT_ID:
        return False
    return True


def _payme_invoice(db: Session, params: dict) -> models.PaymentInvoice:
    """Payme account.order_id bo'yicha schyot-fakturani topadi"""
    account = params.get("account") or {}
    order_id = str(account.get("order_id", ""))
    invoice = db.query(models.PaymentInvoice).filter(
        models.PaymentInvoice.invoice_id == order_id,
        models.PaymentInvoice.gateway == "payme",
    ).first()
    return invoice


def _payme_validate_amount(db: Session, params: dict, rpc_id):
    """CheckPerformTransaction / CreateTransaction uchun summa tekshiruvi"""
    invoice = _payme_invoice(db, params)
    if not invoice:
        return _payme_error(rpc_id, -31050, "Buyurtma topilmadi", "order_id")
    amount_tiyin = int(params.get("amount", 0) or 0)
    if amount_tiyin != int(round(invoice.amount * 100)):
        return _payme_error(rpc_id, -31001, "Noto'g'ri summa")
    return invoice


@router.post("/payme")
async def payme_webhook(request: Request, db: Session = Depends(get_db)):
    """Payme Merchant API webhook (JSON-RPC 2.0)"""
    if not _payme_authorized(request):
        return JSONResponse(status_code=401, content={"error": "Noto'g'ri autentifikatsiya"})

    try:
        body = await request.json()
    except Exception:
        return _payme_rpc(0, error={"code": -32700, "message": "Parse error"})

    rpc_id = body.get("id", 0)
    method = body.get("method", "")
    params = body.get("params", {}) or {}

    try:
        if method == "CheckPerformTransaction":
            invoice = _payme_validate_amount(db, params, rpc_id)
            if isinstance(invoice, JSONResponse):
                return invoice
            return _payme_rpc(rpc_id, result={"allow": True})

        elif method == "CreateTransaction":
            invoice = _payme_validate_amount(db, params, rpc_id)
            if isinstance(invoice, JSONResponse):
                return invoice
            payme_id = str(params.get("id", ""))
            now_ms = int(datetime.now().timestamp() * 1000)
            # Tranzaksiya allaqachon yaratilgan bo'lsa, xuddi shu natijani qaytaramiz
            if invoice.payme_trans_id:
                return _payme_rpc(rpc_id, result={
                    "create_time": invoice.create_time or now_ms,
                    "transaction": invoice.invoice_id,
                    "state": invoice.payme_state
                                if invoice.payme_state is not None
                                else PAYME_STATE_CREATED,
                })
            invoice.payme_trans_id = payme_id
            invoice.create_time = now_ms
            invoice.payme_state = PAYME_STATE_CREATED
            db.commit()
            return _payme_rpc(rpc_id, result={
                "create_time": now_ms,
                "transaction": invoice.invoice_id,
                "state": PAYME_STATE_CREATED,
            })

        elif method == "PerformTransaction":
            invoice = _payme_invoice(db, params)
            if not invoice:
                return _payme_error(rpc_id, -31050, "Buyurtma topilmadi", "order_id")
            now_ms = int(datetime.now().timestamp() * 1000)
            if invoice.payme_state == PAYME_STATE_PERFORMED:
                # Idempotent — allaqachon bajarilgan
                return _payme_rpc(rpc_id, result={
                    "perform_time": invoice.perform_time or now_ms,
                    "transaction": invoice.invoice_id,
                    "state": PAYME_STATE_PERFORMED,
                })
            invoice.payme_state = PAYME_STATE_PERFORMED
            invoice.perform_time = now_ms
            db.commit()
            _confirm_payment(db, invoice, gateway="payme")
            return _payme_rpc(rpc_id, result={
                "perform_time": now_ms,
                "transaction": invoice.invoice_id,
                "state": PAYME_STATE_PERFORMED,
            })

        elif method == "CancelTransaction":
            invoice = _payme_invoice(db, params)
            if not invoice:
                return _payme_error(rpc_id, -31050, "Buyurtma topilmadi", "order_id")
            reason = int(params.get("reason", 0) or 0)
            now_ms = int(datetime.now().timestamp() * 1000)
            if invoice.payme_state == PAYME_STATE_PERFORMED:
                # To'langan tranzaksiyani bekor qilib bo'lmaydi
                return _payme_rpc(rpc_id, result={
                    "cancel_time": now_ms,
                    "transaction": invoice.invoice_id,
                    "state": PAYME_STATE_PERFORMED,
                })
            state = PAYME_STATE_CANCELLED_TIMEOUT if reason == 4 else PAYME_STATE_CANCELLED
            invoice.payme_state = state
            invoice.cancel_time = now_ms
            if invoice.status == "pending":
                invoice.status = "cancelled"
            db.commit()
            return _payme_rpc(rpc_id, result={
                "cancel_time": now_ms,
                "transaction": invoice.invoice_id,
                "state": state,
            })

        elif method == "CheckTransaction":
            invoice = _payme_invoice(db, params)
            if not invoice:
                return _payme_error(rpc_id, -31050, "Buyurtma topilmadi", "order_id")
            return _payme_rpc(rpc_id, result={
                "create_time": invoice.create_time or 0,
                "perform_time": invoice.perform_time or 0,
                "cancel_time": invoice.cancel_time or 0,
                "transaction": invoice.invoice_id,
                "state": invoice.payme_state
                            if invoice.payme_state is not None
                            else PAYME_STATE_CREATED,
            })

        elif method == "GetStatement":
            # To'lov ko'chirmasi — hozircha shart emas, bo'sh qaytaramiz
            return _payme_rpc(rpc_id, result={"transactions": []})

        return _payme_error(rpc_id, -32601, "Method not found")

    except Exception as e:
        logger.exception("Payme webhook xatosi: %s", e)
        return _payme_error(rpc_id, -31008, "Amalni bajarib bo'lmadi")