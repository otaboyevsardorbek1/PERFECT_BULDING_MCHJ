"""
Web Dashboard - Qurilish Korxonasi Boshqaruv Paneli
FastAPI asosida yaratilgan web dashboard
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, date, timedelta
import json
import os
import sys

# Loyiha yo'llarini qo'shish
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_DIR, SYSTEM_SETTINGS
from database.session import get_db_session
from database import crud, models

# FastAPI ilova yaratish
app = FastAPI(
    title="🏗️ Qurilish Korxonasi Dashboard",
    description="Boshqaruv paneli va statistika",
    version="1.0.0"
)

# Static fayllar
STATIC_DIR = BASE_DIR / "dashboard" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# HTML shablonlar
TEMPLATES_DIR = BASE_DIR / "dashboard" / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Asosiy dashboard sahifasi"""
    
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
        
        html_content += f"""
                        <tr>
                            <td>{order.order_number or f'#{order.id}'}</td>
                            <td>{product.name if product else 'Noma\'lum'}</td>
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
async def api_stats():
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
async def api_warehouse():
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
async def api_products():
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
async def api_orders():
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
