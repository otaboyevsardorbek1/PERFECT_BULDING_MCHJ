"""
CRUD v5.5 — TZ 3-bo'limdagi qolgan funksional bo'shliqlar (3.9–3.12):

- 3.9  AI/ML moduli: sotuv prognozi (sotuvchi ehtimoli), mijoz segmentatsiyasi,
       dinamik narxlash tavsiyasi, o'xshash mijozlar asosida mahsulot tavsiyasi,
       yetkazib berish ETA bashorati
- 3.10 IoT sensorlar: o'lchovlarni saqlash, saqlash sharti buzilishini aniqlash
- 3.11 Event audit: SystemLog orqali to'liq harakat tarixi (o'chirilmaydigan)
- 3.12 Feature Flags: yoqish/o'chirish, foizli rollout, xato bo'lsa avto-o'chirish

Barcha hisoblar **statistik** — tashqi kutubxona (numpy/pandas) talab qilmaydi.
Mavjud `crud.py`/`crud_v5.py` bilan bir xil uslubda ishlaydi.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from . import models


# ================= 3.9.1 SOTUV PROGNOZI (sotuv hajmi bashorati) =================
def sales_forecast(db: Session, days: int = 30, product_id: Optional[int] = None,
                   category: Optional[str] = None) -> Dict:
    """O'tgan davr savdolari asosida kelgusi kunlar uchun sodda prognoz.

    Metod: o'rtacha kunlik savdo + oxirgi haftaning trendi + hafta oxiri omili.
    """
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(models.Sale).filter(
        models.Sale.sale_date >= since,
        models.Sale.status == "completed",
    )
    if product_id:
        q = q.filter(models.Sale.product_id == product_id)
    sales = q.all()

    # Kategoriya bo'yicha filtr (mahsulotlarni olib, id larini ajratib olamiz)
    if category:
        cat_ids = {p.id for p in db.query(models.Product).filter(
            models.Product.category == category).all()}
        sales = [s for s in sales if s.product_id in cat_ids]

    if not sales:
        return {
            "days_analyzed": days, "product_id": product_id, "category": category,
            "total_revenue": 0, "order_count": 0, "avg_daily_revenue": 0,
            "trend_percent": 0, "trend_label": "barqaror",
            "forecast_7d_revenue": 0, "forecast_30d_revenue": 0,
            "seasonal_note": "Ma'lumot yetarli emas — sotuvlar to'plangach prognoz aniqlashadi.",
            "confidence": 0,
        }

    total_revenue = float(sum(s.total_amount for s in sales))
    order_count = len(sales)
    avg_daily = total_revenue / max(days, 1)

    # Trend: oxirgi 25% davr va undan oldingi 25% davrni solishtirish
    sorted_sales = sorted(sales, key=lambda s: s.sale_date)
    third = max(len(sorted_sales) // 4, 1)
    early = sorted_sales[:third]
    late = sorted_sales[-third:]
    early_sum = sum(s.total_amount for s in early) or 0
    late_sum = sum(s.total_amount for s in late) or 0
    trend_percent = 0.0
    if early_sum > 0:
        trend_percent = round(((late_sum - early_sum) / early_sum) * 100, 1)
    trend_label = "osmoqda" if trend_percent > 5 else (
        "kamaymoqda" if trend_percent < -5 else "barqaror")

    # Hafta kunlari omili (dam olish kunlari qurilish savdosi past bo'ladi)
    weekend_factor = 1.0
    weekend_sales = [s for s in sales if s.sale_date.weekday() >= 5]
    if weekend_sales:
        weekend_avg_per_day = sum(s.total_amount for s in weekend_sales) / max(
            days * 2 / 7, 1)
        weekday_avg_per_day = (total_revenue - sum(s.total_amount for s in weekend_sales)) / max(days * 5 / 7, 1)
        if weekday_avg_per_day > 0:
            weekend_factor = round(weekend_avg_per_day / weekday_avg_per_day, 2)

    forecast_7d = avg_daily * 7 * (1 + trend_percent / 100 / 4)  # trendning 1/4 ta'siri
    forecast_30d = avg_daily * 30 * (1 + trend_percent / 100 / 4)
    confidence = min(90, max(35, int(50 + abs(trend_percent) * 0.3 + min(order_count / 10, 20))))

    seasonal_note = ""
    month = datetime.utcnow().month
    if month in (12, 1, 2):
        seasonal_note = "Qish mavsumi: qurilish faolligi past — prognoz konservativ."
    elif month in (3, 4, 5):
        seasonal_note = "Bahor: qurilish mavsumi ochilmoqda — prognoz optimistik."
    elif month in (6, 7, 8):
        seasonal_note = "Yoz: eng yuqori mavsum — prognoz yuqori talabni ko'rsatadi."
    else:
        seasonal_note = "Kuz: mavsum sekin pasaymoqda."

    return {
        "days_analyzed": days,
        "product_id": product_id,
        "category": category,
        "total_revenue": round(total_revenue, 2),
        "order_count": order_count,
        "avg_daily_revenue": round(avg_daily, 2),
        "trend_percent": trend_percent,
        "trend_label": trend_label,
        "weekend_factor": weekend_factor,
        "forecast_7d_revenue": round(forecast_7d, 2),
        "forecast_30d_revenue": round(forecast_30d, 2),
        "seasonal_note": seasonal_note,
        "confidence": confidence,
    }


# ================= 3.9.2 MIJOZ SEGMENTATSIYASI (klasterlash) =================
def customer_segments(db: Session, min_purchases: float = 0.0) -> Dict:
    """Mijozlarni xarid summasi, chek soni va qarz xatti-harakati bo'yicha
    avtomatik klasterlash (TZ: "AI asosida segmentatsiya").

    Klasterlar:
      - "vip_oligarcha"  — juda katta xarid + kam qarz
      - "sodiqlangan"    — yuqori xarid, muntazam
      - "potentsial"     — o'rtacha xarid
      - "xavfli_qarzdor" — qarzi xaridining yarmidan oshgan yoki muddati o'tgan
      - "yashirin"       — kam xarid, uzoq vaqt faol bo'lmagan
    """
    customers = db.query(models.Customer).all()
    segments: Dict[str, List[Dict]] = {k: [] for k in (
        "vip_oligarcha", "sodiqlangan", "potentsial", "xavfli_qarzdor", "yashirin")}

    now = datetime.utcnow()
    for c in customers:
        sales = [s for s in (c.sales or []) if s.status == "completed"]
        check_count = len(sales)
        total_purchases = float(sum(s.total_amount for s in sales))
        debt = float(c.total_debt or 0)
        overdue = any(s.credit_status == "muddati_otgan" for s in sales)
        last_sale = max((s.sale_date for s in sales), default=None)
        days_inactive = (now - last_sale).days if last_sale else 999
        avg_check = total_purchases / check_count if check_count else 0

        if debt > total_purchases * 0.5 or overdue:
            seg = "xavfli_qarzdor"
        elif total_purchases >= 50_000_000 and debt < total_purchases * 0.2:
            seg = "vip_oligarcha"
        elif total_purchases >= 10_000_000 or check_count >= 10:
            seg = "sodiqlangan"
        elif days_inactive > 90:
            seg = "yashirin"
        else:
            seg = "potentsial"

        if total_purchases < min_purchases and seg != "xavfli_qarzdor":
            continue
        segments[seg].append({
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "total_purchases": total_purchases,
            "check_count": check_count,
            "avg_check": round(avg_check, 2),
            "debt": debt,
            "overdue": overdue,
            "days_inactive": days_inactive if last_sale else None,
            "loyalty_points": float(c.loyalty_points or 0),
            "tier": getattr(c, "tier", None),
        })

    # Har segmentda xarid bo'yicha kamayish tartibida
    for seg in segments:
        segments[seg].sort(key=lambda x: x["total_purchases"], reverse=True)

    recommendations = {
        "vip_oligarcha": "Shaxsiy menejer, maxsus narxlar, 24/7 qo'llab-quvvatlash",
        "sodiqlangan": "Sodiqlik bonusi, ommaviy aksiyalardan xabardor qilish",
        "potentsial": "O'xshash mahsulot takliflari, o'sish uchun motivatsiya",
        "xavfli_qarzdor": "Qarz eslatmasi (SMS), yangi nasiyani bloklash, direktor nazorati",
        "yashirin": "'Qaytib kel' kupon yuborish (TZ: 3 oy xarid qilmasa)",
    }

    return {
        "total_customers": len(customers),
        "segments": {k: v for k, v in segments.items()},
        "summary": {k: len(v) for k, v in segments.items()},
        "recommendations": recommendations,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ================= 3.9.3 DINAMIK NARXLASH TAVSIYASI =================
def dynamic_pricing_suggestion(db: Session, product_id: Optional[int] = None) -> Dict:
    """Qoldiq va talabga qarab narxni moslash tavsiyasi (TZ 3.1/3.9:
    "Dinamik narxlash — ombordagi qoldiq va talabga qarab narxni avtomatik
    moslash (direktor tasdig'i bilan)").

    Qoidalar (o'rtacha kunlik sotuvga nisbatan):
      - qoldiq > 60 kunlik talab  → narxni 5% tushirish tavsiya
      - qoldiq < 14 kunlik talab  → narxni 3% oshirish tavsiya
      - aks holda                 → narxni saqlash
    """
    q = db.query(models.Product).filter(models.Product.is_active.is_(True))
    if product_id:
        q = q.filter(models.Product.id == product_id)
    products = q.all()

    suggestions = []
    for p in products:
        # Mahsulot qoldig'i: kirim-chiqim harakatlaridan hisoblash
        balance = db.query(
            func.sum(models.WarehouseTransaction.quantity)).filter(
            models.WarehouseTransaction.product_id == p.id,
            models.WarehouseTransaction.transaction_type.in_(
                [models.TransactionType.INCOME, models.TransactionType.PRODUCTION,
                 models.TransactionType.RETURN]),
        ).scalar() or 0
        out = db.query(
            func.sum(models.WarehouseTransaction.quantity)).filter(
            models.WarehouseTransaction.product_id == p.id,
            models.WarehouseTransaction.transaction_type.in_(
                [models.TransactionType.OUTCOME, models.TransactionType.SALE]),
        ).scalar() or 0
        stock = float(balance) - float(out)

        # O'tgan 30 kunlik sotuv (kunlik talab)
        since = datetime.utcnow() - timedelta(days=30)
        sold_30d = db.query(func.sum(models.Sale.quantity)).filter(
            models.Sale.product_id == p.id,
            models.Sale.sale_date >= since,
            models.Sale.status == "completed",
        ).scalar() or 0
        daily_demand = float(sold_30d) / 30.0

        action = "saqlash"
        price_change_percent = 0
        days_of_stock = None
        if daily_demand > 0:
            days_of_stock = round(stock / daily_demand, 1)
            if days_of_stock > 60:
                action = "pasaytirish"
                price_change_percent = 5
            elif days_of_stock < 14:
                action = "oshirish"
                price_change_percent = 3

        base_price = p.selling_price or p.retail_price or 0
        suggestions.append({
            "product_id": p.id,
            "product_name": p.name,
            "category": p.category,
            "stock": round(stock, 2),
            "daily_demand": round(daily_demand, 3),
            "days_of_stock": days_of_stock,
            "current_price": base_price,
            "action": action,
            "action_label": {
                "pasaytirish": "📉 Narxni tushirish",
                "oshirish": "📈 Narxni oshirish",
                "saqlash": "➖ Saqlash",
            }[action],
            "suggested_price": round(base_price * (1 + price_change_percent / 100), 2)
            if action != "saqlash" else base_price,
            "price_change_percent": price_change_percent,
            "requires_director_approval": action != "saqlash",
        })

    suggestions.sort(key=lambda s: (s["action"] == "saqlash", -abs(s["price_change_percent"])))
    return {
        "suggestions": suggestions,
        "note": "Tavsiyalar tarixiy ma'lumotga asoslangan — narxni o'zgartirishdan "
                "oldin direktor tasdig'i kerak (narx tarixi avtomatik saqlanadi).",
    }


# ================= 3.9.4 O'XSHASH MIJOZLAR → MAHSULOT TAVSIYASI =================
def recommend_products_for_customer(db: Session, customer_id: int,
                                    limit: int = 5) -> Dict:
    """Xarid tarixi va o'xshash mijozlar asosida mahsulot tavsiyasi (TZ 3.6/3.9:
    "AI tavsiyalar — mijozning xarid tarixiga asoslanib...").

    Metod (collaborative filtering'ning sodda shakli):
      1. Mijoz olgan mahsulot kategoriyalari aniqlanadi.
      2. O'sha kategoriyalarni (yoki mahsulotlarni) olgan boshqa mijozlar
         o'xshash deb topiladi.
      3. O'xshash mijozlar ko'p olgan, ammo bizning mijoz olmagan mahsulotlar
         tavsiya qilinadi.
    """
    customer = db.query(models.Customer).get(customer_id)
    if not customer:
        return {"customer": None, "recommendations": [], "note": "Mijoz topilmadi"}

    my_sales = [s for s in (customer.sales or []) if s.status == "completed"]
    my_product_ids = {s.product_id for s in my_sales}
    my_categories = set()
    for s in my_sales:
        if s.product:
            my_categories.add(s.product.category)

    # O'xshash mijozlar: kamida bitta umumiy kategoriyada xarid qilganlar
    similar_scores: Dict[int, float] = {}
    others = db.query(models.Customer).filter(models.Customer.id != customer_id).all()
    for other in others:
        other_sales = [s for s in (other.sales or []) if s.status == "completed"]
        other_categories = {s.product.category for s in other_sales if s.product}
        overlap = my_categories & other_categories
        if not overlap:
            continue
        jaccard = len(overlap) / max(len(my_categories | other_categories), 1)
        similar_scores[other.id] = jaccard * (1 + len(other_sales) * 0.05)

    # O'xshash mijozlar sotuvlari
    rec_scores: Dict[int, float] = {}
    if similar_scores:
        similar_ids = list(similar_scores.keys())
        cand_sales = db.query(models.Sale).filter(
            models.Sale.customer_id.in_(similar_ids),
            models.Sale.status == "completed",
        ).all()
        for s in cand_sales:
            if s.product_id in my_product_ids:
                continue
            weight = similar_scores.get(s.customer_id, 0)
            rec_scores[s.product_id] = rec_scores.get(s.product_id, 0) + weight * float(s.total_amount) / 1e6

    recommendations = []
    if rec_scores:
        top_ids = [pid for pid, _ in sorted(rec_scores.items(), key=lambda x: -x[1])[:limit]]
        products = db.query(models.Product).filter(models.Product.id.in_(top_ids)).all()
        by_id = {p.id: p for p in products}
        for pid in top_ids:
            p = by_id.get(pid)
            if not p:
                continue
            recommendations.append({
                "product_id": p.id,
                "product_name": p.name,
                "category": p.category,
                "price": p.selling_price or p.retail_price,
                "score": round(rec_scores[pid], 3),
                "reason": "O'xshash mijozlar ko'p xarid qilgan",
            })
    else:
        # Fallback: mijozning kategoriyalaridagi eng ko'p sotilgan mahsulotlar
        top = db.query(
            models.Sale.product_id, func.sum(models.Sale.quantity).label("q")
        ).filter(models.Sale.status == "completed").group_by(
            models.Sale.product_id).order_by(desc("q")).limit(limit).all()
        for pid, _ in top:
            if pid in my_product_ids:
                continue
            p = db.query(models.Product).get(pid)
            if not p:
                continue
            recommendations.append({
                "product_id": p.id,
                "product_name": p.name,
                "category": p.category,
                "price": p.selling_price or p.retail_price,
                "score": 0,
                "reason": "Umumiy TOP sotuvlar (shaxsiy ma'lumot yetarli emas)",
            })

    similar_count = len(similar_scores)
    return {
        "customer": {"id": customer.id, "name": customer.name},
        "purchased_categories": sorted(my_categories),
        "similar_customers_found": similar_count,
        "recommendations": recommendations,
        "note": "Xarid tarixi to'plangani sari tavsiyalar aniqlashadi.",
    }


# ================= 3.9.5 YETKAZIB BERISH ETA BASHORATI =================
def delivery_eta(db: Session, distance_km: float = 10.0,
                 vehicle_id: Optional[int] = None) -> Dict:
    """Yetkazib berish vaqtini bashorat qilish (TZ 3.5/3.9: "Yo'l tirbandligi,
    ob-havo, haydovchi tajribasini hisobga olgan holda aniq vaqtni hisoblash").

    Metod: mashina normasi + shahar ichi/atrof tezligi + yuklash vaqti + mavsumiy omil.
    """
    avg_speed_kmh = 40.0  # shahar ichi o'rtacha
    load_minutes = 25.0   # yuklash/ortish o'rtacha vaqti
    notes = []

    vehicle = None
    if vehicle_id:
        vehicle = db.query(models.Vehicle).get(vehicle_id)
        if vehicle and vehicle.status == "ta'mirda":
            notes.append("⚠️ Mashina ta'mirda — boshqa mashina tanlang.")

    # Mavsumiy omil: qunda qor/yomg'ir tezlikni pasaytiradi
    month = datetime.utcnow().month
    seasonal_factor = {12: 0.8, 1: 0.8, 2: 0.85, 11: 0.9, 3: 0.95}.get(month, 1.0)
    if seasonal_factor < 1.0:
        notes.append(f"❄️ Mavsumiy omil: yo'l sharoiti tezlikni "
                     f"{round((1 - seasonal_factor) * 100)}% pasaytiradi.")

    # Haydovchi tajribasi (yetkazib berishlar soni > 50 bo'lsa yuklash tezroq)
    if vehicle and vehicle.driver_id:
        done_deliveries = db.query(func.count(models.Delivery.id)).filter(
            models.Delivery.driver_id == vehicle.driver_id,
            models.Delivery.status == "yetkazib_berildi",
        ).scalar() or 0
        if done_deliveries > 50:
            load_minutes *= 0.8
            notes.append(f"🏆 Haydovchi tajribali ({done_deliveries} ta yetkazib berish) — yuklash tezroq.")

    effective_speed = avg_speed_kmh * seasonal_factor
    drive_minutes = (distance_km / max(effective_speed, 1)) * 60
    eta_minutes = round(drive_minutes + load_minutes)
    eta_time = datetime.utcnow() + timedelta(minutes=eta_minutes)

    return {
        "distance_km": distance_km,
        "vehicle": {"id": vehicle.id, "number": vehicle.number} if vehicle else None,
        "avg_speed_kmh": round(effective_speed, 1),
        "load_minutes": round(load_minutes),
        "drive_minutes": round(drive_minutes),
        "eta_minutes": eta_minutes,
        "eta_time": eta_time.isoformat(),
        "factors": notes or ["Standart sharoit: tirbandlik/ob-havo omillari neytral."],
    }


# ================= 3.10 IOT SENSORLAR =================
# Saqlash shartlari chegaralari (TZ 3.1: namlik, harorat, yonuvchanlik)
SENSOR_LIMITS = {
    "temperature": {"min": 0, "max": 35, "unit": "°C"},
    "humidity": {"min": 20, "max": 80, "unit": "%"},
}


def add_sensor_reading(db: Session, data: Dict) -> models.SensorReading:
    """Yangi sensor o'lchovini saqlash; me'yordan chiqsa is_out_of_range belgilanadi."""
    sensor_type = str(data.get("sensor_type", "")).strip()
    value = float(data.get("value", 0))
    limits = SENSOR_LIMITS.get(sensor_type)

    out_of_range = False
    if limits:
        out_of_range = value < limits["min"] or value > limits["max"]

    reading = models.SensorReading(
        sensor_type=sensor_type,
        device_name=data.get("device_name"),
        warehouse=data.get("warehouse"),
        value=value,
        unit=data.get("unit") or (limits["unit"] if limits else data.get("unit")),
        is_out_of_range=out_of_range,
        notes=data.get("notes"),
        recorded_by=data.get("recorded_by"),
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


def list_sensor_readings(db: Session, sensor_type: Optional[str] = None,
                         warehouse: Optional[str] = None,
                         out_of_range_only: bool = False,
                         limit: int = 100) -> List[Dict]:
    q = db.query(models.SensorReading)
    if sensor_type:
        q = q.filter(models.SensorReading.sensor_type == sensor_type)
    if warehouse:
        q = q.filter(models.SensorReading.warehouse == warehouse)
    if out_of_range_only:
        q = q.filter(models.SensorReading.is_out_of_range.is_(True))
    rows = q.order_by(desc(models.SensorReading.created_at)).limit(limit).all()
    return [{
        "id": r.id,
        "sensor_type": r.sensor_type,
        "device_name": r.device_name,
        "warehouse": r.warehouse,
        "value": r.value,
        "unit": r.unit,
        "is_out_of_range": r.is_out_of_range,
        "notes": r.notes,
        "recorded_by": r.recorded_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


def sensor_alerts_summary(db: Session) -> Dict:
    """Buzilgan saqlash shartlari xulosasi (TZ: "Saqlash shartlari buzilsa ogohlantirish")."""
    total = db.query(func.count(models.SensorReading.id)).scalar() or 0
    violations = db.query(models.SensorReading).filter(
        models.SensorReading.is_out_of_range.is_(True)
    ).order_by(desc(models.SensorReading.created_at)).limit(50).all()

    by_type: Dict[str, int] = {}
    for v in violations:
        by_type[v.sensor_type] = by_type.get(v.sensor_type, 0) + 1

    return {
        "total_readings": total,
        "violations_count": len(violations),
        "violations_by_type": by_type,
        "recent_violations": [{
            "id": v.id, "sensor_type": v.sensor_type, "device_name": v.device_name,
            "warehouse": v.warehouse, "value": v.value, "unit": v.unit,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        } for v in violations[:10]],
        "note": "Qoidalar: harorat 0–35°C, namlik 20–80%. Saqlash sharti buzilganda "
                "omborchi va direktor ogohlantirilishi kerak (Telegram bildirishnoma).",
    }


# ================= 3.11 EVENT AUDIT (SystemLog asosida) =================
def audit_log(db: Session, module: Optional[str] = None,
              action: Optional[str] = None, limit: int = 200,
              offset: int = 0) -> Dict:
    """To'liq harakat tarixi: kim, qachon, nima qilgani (TZ 3.11: "Audit log").

    SystemLog o'chirilmaydigan append-only jurnal — har bir muhim operatsiya
    (kirim, chiqim, sotuv, narx o'zgarishi, login...) yozib boriladi.
    """
    q = db.query(models.SystemLog)
    if module:
        q = q.filter(models.SystemLog.module == module)
    if action:
        q = q.filter(models.SystemLog.action == action)
    total = q.count()
    rows = q.order_by(desc(models.SystemLog.created_at)).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [{
            "id": r.id,
            "module": r.module,
            "action": r.action,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "details": r.details,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows],
        "note": "Jurnal o'chirilmaydigan (append-only) — soliq tekshiruvi va "
                "xodimlar nizolarida ishonchli dalil.",
    }


# ================= 3.12 FEATURE FLAGS =================
def create_feature_flag(db: Session, key: str, name: str = None,
                        is_enabled: bool = False, rollout_percent: int = 100,
                        auto_disable_on_error: bool = False,
                        created_by: str = None) -> models.FeatureFlag:
    flag = models.FeatureFlag(
        key=key.strip().lower().replace(" ", "_"),
        name=name,
        is_enabled=is_enabled,
        rollout_percent=max(0, min(int(rollout_percent), 100)),
        auto_disable_on_error=auto_disable_on_error,
        created_by=created_by,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return flag


def list_feature_flags(db: Session) -> List[models.FeatureFlag]:
    return db.query(models.FeatureFlag).order_by(models.FeatureFlag.key).all()


def update_feature_flag(db: Session, flag_id: int, data: Dict) -> Optional[models.FeatureFlag]:
    flag = db.query(models.FeatureFlag).get(flag_id)
    if not flag:
        return None
    if "is_enabled" in data:
        flag.is_enabled = bool(data["is_enabled"])
    if "rollout_percent" in data:
        flag.rollout_percent = max(0, min(int(data["rollout_percent"]), 100))
    if "name" in data and data["name"]:
        flag.name = data["name"]
    if "auto_disable_on_error" in data:
        flag.auto_disable_on_error = bool(data["auto_disable_on_error"])
    db.commit()
    db.refresh(flag)
    return flag


def delete_feature_flag(db: Session, flag_id: int) -> bool:
    flag = db.query(models.FeatureFlag).get(flag_id)
    if not flag:
        return False
    db.delete(flag)
    db.commit()
    return True


def is_feature_enabled(db: Session, key: str, user_seed: int = 0) -> Dict:
    """Flag holatini tekshirish (foizli rollout: user_seed % 100 < rollout_percent).

    user_seed — foydalanuvchi/barqaror identifikator (masalan employee.id).
    """
    flag = db.query(models.FeatureFlag).filter(models.FeatureFlag.key == key).first()
    if not flag:
        return {"key": key, "enabled": False, "exists": False,
                "reason": "Flag topilmadi (default: o'chirilgan)"}
    if not flag.is_enabled:
        return {"key": key, "enabled": False, "exists": True,
                "reason": "Flag o'chirilgan"}
    if user_seed % 100 >= flag.rollout_percent:
        return {"key": key, "enabled": False, "exists": True,
                "reason": f"Rollout {flag.rollout_percent}% — bu foydalanuvchiga yo'q"}
    return {"key": key, "enabled": True, "exists": True,
            "reason": "OK", "rollout_percent": flag.rollout_percent}


def record_feature_error(db: Session, key: str, threshold: int = 5) -> Dict:
    """Xatoni qayd etish; ketma-ket xatolar threshold'dan oshsa flag avto-o'chiriladi
    (TZ 3.12: "Xato yuz bersa, xususiyatni avtomatik o'chirish")."""
    flag = db.query(models.FeatureFlag).filter(models.FeatureFlag.key == key).first()
    if not flag:
        return {"key": key, "auto_disabled": False, "exists": False}
    flag.error_count = (flag.error_count or 0) + 1
    auto_disabled = False
    if flag.auto_disable_on_error and flag.error_count >= threshold:
        flag.is_enabled = False
        auto_disabled = True
    db.commit()
    db.refresh(flag)
    return {
        "key": key, "exists": True, "error_count": flag.error_count,
        "threshold": threshold, "auto_disabled": auto_disabled,
        "is_enabled": flag.is_enabled,
    }
