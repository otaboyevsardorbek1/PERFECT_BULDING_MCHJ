"""
Feature Flags yordamchisi — TZ 3.12 ("Xususiyatlarni boshqarish")

Funksional xususiyatlarni kod ichidan tekshirish uchun qisqa keshli qatlam:

    from utils.feature_flags import is_feature_enabled

    if is_feature_enabled("ai_recommendations", user_seed=emp.id):
        ...

Kesh `FEATURE_FLAG_CACHE_TTL` soniya davomida yashaydi (default 30 s) —
flag holati tez-tez so'ralganda ham DB yuklanmasligi uchun.
"""
import logging
import os
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

CACHE_TTL = int(os.getenv("FEATURE_FLAG_CACHE_TTL", "30"))
_cache: Dict[str, tuple] = {}  # key -> (expires_at, result_dict)
_lock = threading.Lock()


def _from_cache(key: str) -> Optional[Dict]:
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, result = entry
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    return result


def _to_cache(key: str, result: Dict) -> Dict:
    with _lock:
        _cache[key] = (time.time() + CACHE_TTL, result)
    return result


def clear_cache():
    """Flag o'zgarsa keshni tozalash (API PATCH flag bo'lganda chaqiriladi)."""
    with _lock:
        _cache.clear()


def is_feature_enabled(key: str, user_seed: int = 0) -> bool:
    """Flag yoqilganmi? (kesh bilan; DB xatosida xavfsiz javob — False)."""
    full = evaluate_flag(key, user_seed=user_seed)
    return bool(full.get("enabled"))


def evaluate_flag(key: str, user_seed: int = 0) -> Dict:
    """To'liq flag holati: {key, enabled, exists, reason}."""
    cache_key = f"{key}:{int(user_seed) % 100}"
    cached = _from_cache(cache_key)
    if cached is not None:
        return cached
    try:
        from database.session import get_db_session
        from database import crud_v55
        with get_db_session() as db:
            result = crud_v55.is_feature_enabled(db, key, user_seed=user_seed)
        return _to_cache(cache_key, result)
    except Exception as e:  # DB yo'q/ko'chib o'tish paytida ham ishlashi kerak
        logger.warning(f"Feature flag '{key}' tekshiruvida xato: {e}")
        return {"key": key, "enabled": False, "exists": False,
                "reason": f"Tekshiruv xatosi: {e}"}


def record_error(key: str, threshold: int = 5) -> Dict:
    """Xususiyatda xato ro'y berganda chaqiriladi — ketma-ket xatolarda
    flag avtomatik o'chadi (TZ 3.12: "Avtomatik o'chirish")."""
    clear_cache()
    try:
        from database.session import get_db_session
        from database import crud_v55
        with get_db_session() as db:
            return crud_v55.record_feature_error(db, key, threshold=threshold)
    except Exception as e:
        logger.warning(f"Feature flag '{key}' xatosini yozishda muammo: {e}")
        return {"key": key, "auto_disabled": False, "exists": False, "error": str(e)}
