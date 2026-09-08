"""
Web Dashboard - Qurilish Korxonasi Boshqaruv Paneli
FastAPI asosida yaratilgan web dashboard
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, date, timedelta
import json
import os
import sys

# Loyiha yo'llarini qo'shish
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from config import BASE_DIR, SYSTEM_SETTINGS, WEB_SETTINGS, role_can_view
from database.session import get_db, get_db_session
from database import crud, models
from dashboard.auth import (
    AuthUser, TOKEN_TTL_SECONDS, WEB_TOKEN_COOKIE, create_web_session,
    decode_token, employee_2fa_enabled, find_employee_by_phone, get_web_user,
    issue_2fa_pending_token, require_role, revoke_session, strip_cost_fields,
    verify_2fa_code, verify_password,
)

# =============== TANNARX MAYDONLARINI YASHIRISH (server tomonda) ===============
# see_cost=False rollar (sotuvchi, kassir, omborchi, haydovchi, ishchi) tannarx/narx
# ma'lumotlarini frontend'da yashirish orqali emas, SERVER darajasida ololmasligi kerak.
# Bu middleware /api JSON javoblaridan tannarx maydonlarini olib tashlaydi.
class CostVisibilityMiddleware(BaseHTTPMiddleware):
    """see_cost=False foydalanuvchiga tannarx maydonlarini hech qachon qaytarmaydi."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Faqat muvaffaqiyatli /api JSON javoblarini filtrlash
        if response.status_code >= 400:
            return response
        if not request.url.path.startswith("/api"):
            return response
        if "application/json" not in response.headers.get("content-type", ""):
            return response

        # Foydalanuvchi kirganmi? (get_current_user request.state.auth_user'ni to'ldiradi)
        user = getattr(request.state, "auth_user", None)
        if user is None or getattr(user, "see_cost", True):
            return response

        # Javob tanasini o'qib, tannarx maydonlarini olib tashlash
        body = b"".join([chunk async for chunk in response.body_iterator])
        if not body:
            return response
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return response

        cleaned = strip_cost_fields(payload, user)
        new_body = json.dumps(cleaned, ensure_ascii=False).encode("utf-8")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(content=new_body, status_code=response.status_code,
                        headers=headers, media_type="application/json")


# =============== RATE LIMITING (xavfsizlik) ===============
# Har bir IP uchun daqiqada so'rovlar sonini cheklaydi (brute force/DoS'dan himoya)
class RateLimitMiddleware(BaseHTTPMiddleware):
    """API so'rovlarini IP va yo'l bo'yicha chegara bilan cheklaydi."""

    def __init__(self, app, per_minute: int = 300, per_minute_login: int = 10):
        super().__init__(app)
        self.per_minute = per_minute
        self.per_minute_login = per_minute_login
        self._hits = {}

    def _key(self, request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        return f"{ip}:{request.url.path}"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)

        # Test muhitida rate limit o'chiriladi (testlar ko'p so'rov yuboradi)
        if os.environ.get("TEST_MODE") == "true":
            return await call_next(request)

        key = self._key(request)
        now = int(datetime.now().timestamp())
        limit = self.per_minute_login if path.endswith("/login") or path.endswith("/refresh") else self.per_minute

        stamps = self._hits.get(key, [])
        stamps = [s for s in stamps if s > now - 60]
        if len(stamps) >= limit:
            return JSONResponse(
                status_code=429,
                content={"error": "So'rovlar soni limitdan oshdi. Bir daqiqadan keyin qayta urinib ko'ring."},
            )
        stamps.append(now)
        self._hits[key] = stamps
        return await call_next(request)


# FastAPI ilova yaratish
app = FastAPI(
    title="🏗️ Qurilish Korxonasi Dashboard",
    description="Boshqaruv paneli, statistika va REST API (v3)",
    version="3.0.0"
)

# CORS — Node.js frontend (localhost:3000) uchun
app.add_middleware(
    CORSMiddleware,
    allow_origins=WEB_SETTINGS["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Xavfsizlik: rate limiting — IP bo'yicha so'rovlar chegarasi
app.add_middleware(RateLimitMiddleware)

# Server tomonda tannarx filtri (see_cost=False rollar uchun)
app.add_middleware(CostVisibilityMiddleware)

# REST API v3 router (Node.js frontend foydalanadi)
# v5 router avval ro'yxatdan o'tadi: literal yo'llar (masalan /customers/debtors,
# /orders/sales) v3 dagi {customer_id}/{order_number} parametrli yo'llardan ustun turadi.
from dashboard.api_v5 import router as api_v5_router
app.include_router(api_v5_router)
from dashboard.api_v3 import router as api_v3_router
app.include_router(api_v3_router)

# Onlayn to'lovlar webhook'lari (Click / Payme) — auth talab qilmaydi, imzo bilan tekshiriladi
from dashboard.payments import router as payments_router
app.include_router(payments_router)

# Ommaviy web-do'kon (catalog/savat/checkout) — auth talab qilmaydi
from dashboard.shop import router as shop_router
app.include_router(shop_router)


@app.exception_handler(HTTPException)
async def http_exception_json_handler(request: Request, exc: HTTPException):
    """HTTP xatolarni yagona JSON shaklga keltirish: {"error": ...}"""
    return JSONResponse(status_code=exc.status_code,
                        content={"error": exc.detail} if isinstance(exc.detail, str) else {"error": exc.detail})

# Database schema'ni avtomatik yangilash (mavjud construction.db o'chirilmaydi)
try:
    models.upgrade_schema()
except Exception as e:
    print(f"Schema yangilashda xatolik: {e}")

# Web dashboard parollari (v3 auth) — WEB_ADMIN_PASSWORD env berilgan bo'lsa
# paroli yo'q admin xodimlarga avtomatik o'rnatiladi (birinchi ishga tushirish)
try:
    from dashboard.auth import bootstrap_admin_passwords
    _boot_count = bootstrap_admin_passwords()
    if _boot_count:
        print(f"🔐 WEB_ADMIN_PASSWORD {_boot_count} ta admin xodimga o'rnatildi")
except Exception as e:
    print(f"Parol bootstrap xatosi: {e}")


# Static fayllar
STATIC_DIR = BASE_DIR / "dashboard" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# HTML shablonlar
TEMPLATES_DIR = BASE_DIR / "dashboard" / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============== LEGACY HTML SAHIFA AUTH (root dashboard) ===============
def _login_page_html(error: str = "", need_otp: bool = False,
                     otp_token: str = "") -> str:
    """Login sahifasi.

    - Oddiy hol: xodim telefoni + web parol.
    - need_otp=True: parol to'g'ri kiritilgan, endi Google Authenticator kodini
      so'raymiz (otp_token yashirin maydonda — parol qayta so'ralmaydi).
    """
    err_block = (
        f'<div style="background:#f8d7da;color:#721c24;padding:10px 14px;'
        f'border-radius:8px;margin-bottom:16px;font-size:0.95em;">{error}</div>'
        if error else ""
    )
    if need_otp:
        fields = (
            f'<input type="hidden" name="otp_token" value="{otp_token}">'
            f'<label for="otp_code">🔢 Google Authenticator kodi</label>'
            f'<input type="text" id="otp_code" name="otp_code" placeholder="6 xonali kod" '
            f'autocomplete="one-time-code" inputmode="numeric" maxlength="6" required>'
            f'<button type="submit">Tasdiqlash</button>'
            f'<div class="hint">Telefoningizdagi Google Authenticator ilovasidan joriy 6 xonali kodni kiriting.</div>'
        )
    else:
        fields = (
            f'<label for="phone">📱 Telefon raqami</label>'
            f'<input type="text" id="phone" name="phone" placeholder="+998901234567" '
            f'autocomplete="username" required>'
            f'<label for="password">🔑 Parol</label>'
            f'<input type="password" id="password" name="password" placeholder="Web parol" '
            f'autocomplete="current-password" required>'
            f'<button type="submit">Kirish</button>'
            f'<div class="hint">Xodim telefoni va web paroli ishlatiladi.<br>Parol o\'rnatilmagan bo\'lsa, admin bilan bog\'laning.</div>'
        )
    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔐 Kirish — Qurilish Korxonasi</title>
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{
                font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;
                background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                min-height:100vh; display:flex; align-items:center; justify-content:center;
                padding:20px;
            }}
            .login-box {{
                background:#fff; border-radius:16px; padding:36px; width:100%;
                max-width:400px; box-shadow:0 15px 40px rgba(0,0,0,.25);
            }}
            .login-box h1 {{ font-size:1.5em; color:#333; margin-bottom:6px; text-align:center; }}
            .login-box p.sub {{ color:#888; font-size:.9em; margin-bottom:22px; text-align:center; }}
            .login-box label {{ display:block; font-size:.85em; color:#555; margin:14px 0 6px; }}
            .login-box input {{
                width:100%; padding:11px 12px; border:1px solid #ddd; border-radius:8px;
                font-size:1em; outline:none;
            }}
            .login-box input:focus {{ border-color:#667eea; }}
            .login-box button {{
                width:100%; margin-top:20px; padding:12px; background:#667eea; color:#fff;
                border:none; border-radius:8px; font-size:1.05em; cursor:pointer;
            }}
            .login-box button:hover {{ background:#5a6fd6; }}
            .hint {{ margin-top:16px; font-size:.78em; color:#999; text-align:center; line-height:1.5; }}
        </style>
    </head>
    <body>
        <form class="login-box" method="post" action="/login">
            <h1>🏗️ Qurilish Korxonasi</h1>
            <p class="sub">Dashboard'ga kirish</p>
            {err_block}
            {fields}
        </form>
    </body>
    </html>
    """


def _denied_page_html(user: AuthUser) -> str:
    """Kirgan, lekin ruxsati yo'q foydalanuvchi uchun sahifa"""
    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head><meta charset="UTF-8"><title>Ruxsat yo'q</title></head>
    <body style="font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;margin:0">
      <div style="background:#fff;border-radius:14px;padding:32px;max-width:420px;text-align:center">
        <h2>🚫 Ruxsat yo'q</h2>
        <p style="color:#666">Assalomu alaykum, {user.full_name}! Sizning rolingiz ({user.role}) ushbu dashboard bo'limini ko'rishga ruxsat bermaydi.</p>
        <a href="/logout" style="display:inline-block;margin-top:14px;padding:10px 18px;background:#667eea;color:#fff;border-radius:8px;text-decoration:none">Chiqish</a>
      </div>
    </body>
    </html>
    """


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    """Login sahifasi — allaqachon kirgan bo'lsa dashboard'ga o'tkazadi"""
    user = get_web_user(request, db)
    if user is not None:
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(content=_login_page_html())


@app.post("/login")
async def login_submit(request: Request, db: Session = Depends(get_db)):
    """Telefon + parolni (va 2FA bo'lsa Google Authenticator kodini) tekshirib
    web_token cookie'sini o'rnatadi.

    2FA qadam: parol to'g'ri chiqsa va xodimda 2FA yoqilgan bo'lsa, qisqa muddatli
    otp_token beriladi va sahifada kod so'raladi. Kod tasdiqlangach sessiya ochiladi.
    """
    try:
        form = await request.form()
        phone = str(form.get("phone", "")).strip()
        password = str(form.get("password", ""))
        otp_token = str(form.get("otp_token", "")).strip()
        otp_code = str(form.get("otp_code", "")).strip()
    except Exception:
        return HTMLResponse(content=_login_page_html("So'rov noto'g'ri formatda"), status_code=400)

    # --- 2FA bosqichi: parol allaqachon tasdiqlangan, kodni tekshiramiz ---
    if otp_token:
        payload = decode_token(otp_token)
        if not payload or payload.get("purpose") != "2fa_pending" or not payload.get("uid"):
            return HTMLResponse(content=_login_page_html("Sessiya muddati o'tdi. Qayta kiring."), status_code=401)
        employee = db.query(models.Employee).filter(
            models.Employee.id == payload["uid"]
        ).first()
        if not employee or not employee_2fa_enabled(employee):
            return HTMLResponse(content=_login_page_html("2FA holati o'zgardi. Qayta kiring."), status_code=401)
        if not otp_code:
            return HTMLResponse(
                content=_login_page_html("Google Authenticator kodini kiriting", need_otp=True, otp_token=otp_token),
                status_code=400,
            )
        if not verify_2fa_code(employee, otp_code):
            return HTMLResponse(
                content=_login_page_html("Google Authenticator kodi noto'g'ri", need_otp=True, otp_token=otp_token),
                status_code=401,
            )
        token_data = create_web_session(
            db, employee, user_agent=request.headers.get("user-agent", "") or ""
        )
        secure = request.url.scheme == "https"
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            WEB_TOKEN_COOKIE, token_data["access_token"], max_age=TOKEN_TTL_SECONDS,
            httponly=True, samesite="lax", secure=secure, path="/",
        )
        return response

    # --- Oddiy bosqich: telefon + parol ---
    if not phone or not password:
        return HTMLResponse(content=_login_page_html("Telefon va parolni kiriting"), status_code=400)
    employee = find_employee_by_phone(db, phone)
    if not employee or not employee.password_hash or not verify_password(password, employee.password_hash):
        return HTMLResponse(content=_login_page_html("Telefon yoki parol noto'g'ri"), status_code=401)
    # 2FA yoqilgan bo'lsa — kod so'raymiz (parolni qayta so'ramaymiz)
    if employee_2fa_enabled(employee):
        return HTMLResponse(
            content=_login_page_html("", need_otp=True, otp_token=issue_2fa_pending_token(employee.id)),
        )
    token_data = create_web_session(
        db, employee, user_agent=request.headers.get("user-agent", "") or ""
    )
    secure = request.url.scheme == "https"
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        WEB_TOKEN_COOKIE, token_data["access_token"], max_age=TOKEN_TTL_SECONDS,
        httponly=True, samesite="lax", secure=secure, path="/",
    )
    return response


@app.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """Sessiyani revoke qiladi, cookie'ni o'chiradi va login sahifasiga qaytaradi"""
    token = (request.cookies or {}).get(WEB_TOKEN_COOKIE, "") or ""
    if token:
        payload = decode_token(token)
        if payload and payload.get("sid") is not None:
            revoke_session(db, session_id=payload["sid"])
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(WEB_TOKEN_COOKIE, path="/")
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, auth_db: Session = Depends(get_db)):
    """Asosiy dashboard sahifasi (faqat kirgan foydalanuvchilar uchun)"""

    user = get_web_user(request, auth_db)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    # Root sahifa /api/stats bilan bir xil modulga (reports) tegishli
    if not role_can_view(user.role, "reports"):
        return HTMLResponse(content=_denied_page_html(user), status_code=403)

    with get_db_session() as db:
        # Umumiy statistika
        total_products = db.query(models.Product).filter(
            models.Product.is_active == True
        ).count()
        
        total_materials = db.query(models.RawMaterial).count()
        
        total_employees = db.query(models.Employee).filter(
            models.Employee.status == models.EmployeeStatus.ACTIVE
        ).count()
        
        total_orders = db.query(models.ProductionOrder).count()
        
        # Ombor qiymati
        warehouse_stats = crud.get_warehouse_statistics(db)
        
        # So'nggi buyurtmalar
        recent_orders = db.query(models.ProductionOrder).order_by(
            models.ProductionOrder.created_at.desc()
        ).limit(5).all()
        
        # Xom ashyo holati
        low_stock = db.query(models.RawMaterial).filter(
            models.RawMaterial.current_stock <= models.RawMaterial.min_stock
        ).count()
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🏗️ Qurilish Korxonasi Dashboard</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }}
            .header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            .header p {{
                font-size: 1.2em;
                opacity: 0.9;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .stat-card {{
                background: white;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: transform 0.3s ease;
            }}
            .stat-card:hover {{
                transform: translateY(-5px);
            }}
            .stat-card h3 {{
                color: #666;
                font-size: 0.9em;
                text-transform: uppercase;
                margin-bottom: 10px;
            }}
            .stat-card .value {{
                font-size: 2.5em;
                font-weight: bold;
                color: #333;
            }}
            .stat-card .icon {{
                font-size: 2em;
                float: right;
            }}
            .stat-card.warning {{
                border-left: 5px solid #f39c12;
            }}
            .stat-card.success {{
                border-left: 5px solid #27ae60;
            }}
            .stat-card.info {{
                border-left: 5px solid #3498db;
            }}
            .stat-card.danger {{
                border-left: 5px solid #e74c3c;
            }}
            .section {{
                background: white;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }}
            .section h2 {{
                color: #333;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #eee;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }}
            th {{
                background: #f8f9fa;
                font-weight: 600;
                color: #333;
            }}
            tr:hover {{
                background: #f8f9fa;
            }}
            .badge {{
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 0.8em;
                font-weight: 600;
            }}
            .badge-success {{
                background: #d4edda;
                color: #155724;
            }}
            .badge-warning {{
                background: #fff3cd;
                color: #856404;
            }}
            .badge-danger {{
                background: #f8d7da;
                color: #721c24;
            }}
            .chart-container {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }}
            .chart-box {{
                background: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
            }}
            .chart-box h4 {{
                margin-bottom: 15px;
                color: #333;
            }}
            .bar {{
                display: flex;
                align-items: end;
                justify-content: center;
                height: 150px;
                gap: 10px;
            }}
            .bar-item {{
                width: 40px;
                background: linear-gradient(to top, #667eea, #764ba2);
                border-radius: 5px 5px 0 0;
                position: relative;
            }}
            .bar-item span {{
                position: absolute;
                bottom: -25px;
                left: 50%;
                transform: translateX(-50%);
                font-size: 0.8em;
                color: #666;
            }}
            .refresh-btn {{
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 1em;
                margin-top: 20px;
            }}
            .refresh-btn:hover {{
                background: #5a6fd6;
            }}
            .footer {{
                text-align: center;
                color: white;
                margin-top: 30px;
                opacity: 0.8;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Qurilish Korxonasi Dashboard</h1>
                <p>Real vaqtda boshqaruv paneli | {SYSTEM_SETTINGS.get('timezone', 'Asia/Tashkent')}</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card info">
                    <span class="icon">🏭</span>
                    <h3>Mahsulotlar</h3>
                    <div class="value">{total_products}</div>
                </div>
                <div class="stat-card success">
                    <span class="icon">📦</span>
                    <h3>Xom ashyolar</h3>
                    <div class="value">{total_materials}</div>
                </div>
                <div class="stat-card warning">
                    <span class="icon">👥</span>
                    <h3>Xodimlar</h3>
                    <div class="value">{total_employees}</div>
                </div>
                <div class="stat-card {'danger' if low_stock > 0 else 'success'}">
                    <span class="icon">⚠️</span>
                    <h3>Tugayotgan materiallar</h3>
                    <div class="value">{low_stock}</div>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card info">
                    <span class="icon">📋</span>
                    <h3>Jami buyurtmalar</h3>
                    <div class="value">{total_orders}</div>
                </div>
                <div class="stat-card success">
                    <span class="icon">💰</span>
                    <h3>Ombor qiymati</h3>
                    <div class="value">{warehouse_stats['total_raw_materials_value']:,.0f}</div>
                </div>
            </div>
            
            <div class="section">
                <h2>📋 So'nggi buyurtmalar</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Raqam</th>
                            <th>Mahsulot</th>
                            <th>Miqdor</th>
                            <th>Holat</th>
                            <th>Sana</th>
                        </tr>
                    </thead>
                    <tbody>
            """
    
    for order in recent_orders:
        product = db.query(models.Product).filter(
            models.Product.id == order.product_id
        ).first()
        
        status_class = "badge-success" if order.status == models.OrderStatus.COMPLETED else "badge-warning"
        status_text = order.status.value if order.status else "jarayonda"
        
        product_name = product.name if product else "Noma'lum"
        html_content += f"""
                        <tr>
                            <td>{order.order_number or f'#{order.id}'}</td>
                            <td>{product_name}</td>
                            <td>{order.quantity}</td>
                            <td><span class="badge {status_class}">{status_text}</span></td>
                            <td>{order.created_at.strftime('%d.%m.%Y %H:%M') if order.created_at else '-'}</td>
                        </tr>
        """
    
    html_content += f"""
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2>📊 Xom ashyo holati</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Nomi</th>
                            <th>Birlik</th>
                            <th>Qoldiq</th>
                            <th>Min.</th>
                            <th>Holat</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    with get_db_session() as db2:
        materials = db2.query(models.RawMaterial).all()
        for mat in materials:
            status_class = "badge-danger" if mat.current_stock <= mat.min_stock else "badge-success"
            status_text = "Tugayapti" if mat.current_stock <= mat.min_stock else "Yetarli"
            
            html_content += f"""
                        <tr>
                            <td>{mat.name}</td>
                            <td>{mat.unit}</td>
                            <td>{mat.current_stock:,.0f}</td>
                            <td>{mat.min_stock:,.0f}</td>
                            <td><span class="badge {status_class}">{status_text}</span></td>
                        </tr>
            """
    
    html_content += f"""
                    </tbody>
                </table>
            </div>
            
            <div class="chart-container">
                <div class="chart-box">
                    <h4>📦 Xom ashyo qoldiqlari</h4>
                    <div class="bar">
    """
    
    with get_db_session() as db3:
        materials = db3.query(models.RawMaterial).all()
        max_stock = max([m.current_stock for m in materials]) if materials else 1
        
        for mat in materials[:5]:
            height = (mat.current_stock / max_stock * 120) if max_stock > 0 else 0
            html_content += f"""
                        <div class="bar-item" style="height: {height}px;">
                            <span>{mat.name[:6]}</span>
                        </div>
            """
    
    html_content += f"""
                    </div>
                </div>
                <div class="chart-box">
                    <h4>🏭 Mahsulot turlari</h4>
                    <div class="bar">
    """
    
    with get_db_session() as db4:
        products = db4.query(models.Product).filter(
            models.Product.is_active == True
        ).all()
        max_price = max([p.selling_price for p in products]) if products else 1
        
        for prod in products[:5]:
            height = (prod.selling_price / max_price * 120) if max_price > 0 else 0
            html_content += f"""
                        <div class="bar-item" style="height: {height}px;">
                            <span>{prod.name[:6]}</span>
                        </div>
            """
    
    html_content += f"""
                    </div>
                </div>
            </div>
            
            <button class="refresh-btn" onclick="location.reload()">🔄 Yangilash</button>
            
            <div class="footer">
                <p>🏗️ Qurilish Korxonasi Bot Dashboard v1.0</p>
                <p>Oxirgi yangilanish: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@app.get("/api/stats")
async def api_stats(user: AuthUser = Depends(require_role("reports"))):
    """API: Umumiy statistika"""
    
    try:
        with get_db_session() as db:
            stats = {
                "products": db.query(models.Product).filter(
                    models.Product.is_active == True
                ).count(),
                "materials": db.query(models.RawMaterial).count(),
                "employees": db.query(models.Employee).filter(
                    models.Employee.status == models.EmployeeStatus.ACTIVE
                ).count(),
                "orders": db.query(models.ProductionOrder).count(),
                "low_stock": db.query(models.RawMaterial).filter(
                    models.RawMaterial.current_stock <= models.RawMaterial.min_stock
                ).count(),
                "warehouse_value": crud.get_warehouse_statistics(db)['total_raw_materials_value']
            }
        return JSONResponse(content=stats)
    except Exception as e:
        return JSONResponse(content={"error": str(e), "products": 0, "materials": 0, "employees": 0, "orders": 0, "low_stock": 0, "warehouse_value": 0})


@app.get("/api/warehouse")
async def api_warehouse(user: AuthUser = Depends(require_role("warehouse"))):
    """API: Ombor holati"""
    
    try:
        with get_db_session() as db:
            materials = db.query(models.RawMaterial).all()
            
            data = []
            for mat in materials:
                data.append({
                    "id": mat.id,
                    "name": mat.name,
                    "unit": mat.unit,
                    "current_stock": mat.current_stock,
                    "min_stock": mat.min_stock,
                    "price_per_unit": mat.price_per_unit,
                    "value": mat.current_stock * mat.price_per_unit
                })
        return JSONResponse(content={"materials": data})
    except Exception as e:
        return JSONResponse(content={"error": str(e), "materials": []})


@app.get("/api/products")
async def api_products(user: AuthUser = Depends(require_role("production"))):
    """API: Mahsulotlar"""
    
    try:
        with get_db_session() as db:
            products = db.query(models.Product).filter(
                models.Product.is_active == True
            ).all()
        
        data = []
        for prod in products:
            data.append({
                "id": prod.id,
                "name": prod.name,
                "unit": prod.unit,
                "selling_price": prod.selling_price,
                "production_cost": prod.production_cost,
                "profit_margin": prod.profit_margin
            })
        return JSONResponse(content={"products": data})
    except Exception as e:
        return JSONResponse(content={"error": str(e), "products": []})


@app.get("/api/orders")
async def api_orders(user: AuthUser = Depends(require_role("production"))):
    """API: Buyurtmalar"""
    
    try:
        with get_db_session() as db:
            orders = db.query(models.ProductionOrder).order_by(
                models.ProductionOrder.created_at.desc()
            ).limit(20).all()
            
            data = []
            for order in orders:
                product = db.query(models.Product).filter(
                    models.Product.id == order.product_id
                ).first()
                
                data.append({
                    "id": order.id,
                    "order_number": order.order_number,
                    "product_name": product.name if product else "Noma'lum",
                    "quantity": order.quantity,
                    "status": order.status.value if order.status else "jarayonda",
                    "total_cost": order.total_cost or 0,
                    "created_at": order.created_at.isoformat() if order.created_at else None
                })
        return JSONResponse(content={"orders": data})
    except Exception as e:
        return JSONResponse(content={"error": str(e), "orders": []})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
