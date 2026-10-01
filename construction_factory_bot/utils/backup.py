"""
Avtomatik Database Backup — muntazam zaxira nusxa (scheduled auto-backup)

Fon vazifasi (utils/notifications.py -> NotificationManager.send_scheduled_reports)
har 5 daqiqada chaqiriladi; backup BACKUP_SETTINGS["time"] (standart 02:00) da
kuniga bir marta olinadi.

Xususiyatlari:
- SQLite "online backup" API si (sqlite3.Connection.backup) — tizim ishlab
  turgan paytda ham KONSISTENT nusxa olinadi (shutil.copy2 kabi buzilgan fayl emas).
- Fayl nomi: backups/backup_YYYYMMDD_HHMMSS.db
- Eski nusxalar BACKUP_SETTINGS["keep_days"] (30 kun) dan oshsa o'chiriladi.
- BACKUP_SETTINGS["notify_on_backup"] bo'lsa adminlarga Telegram xabar yuboriladi
  va SystemLog'ga yoziladi.

Uzoq joyga yuklash (serverdan tashqarida xavfsiz nusxa):
- BACKUP_UPLOAD_SETTINGS["remote"] = "telegram" | "s3" | "telegram,s3"
  -> har bir backup fayl barcha yoqilgan manzillarga yuboriladi:
  * telegram: belgilangan Telegram kanaliga hujjat sifatida
  * s3: S3-mos bulut (AWS S3 / MinIO / Wasabi / DigitalOcean Spaces...) ga
    SigV4 imzolangan PUT orqali — qo'shimcha kutubxona (boto3) shart EMAS
- BACKUP_ENCRYPTION_PASSWORD paroli qo'yilgan bo'lsa, serverdan chiqadigan har
  bir nusxa SHIFRLANADI (PBKDF2-200k + AES-128-CBC — Fernet): telegram/S3 da
  <nomi>.enc sifatida saqlanadi, lokal nusxa (backups/) ochiq qoladi.
  Shifrni ochish: decrypt_backup_file() — masalan uzoq nusxadan tiklashda.

Uzoq joyda saqlash muddati (retention):
- BACKUP_REMOTE_KEEP_DAYS (standart: BACKUP_KEEP_DAYS, 0 = o'chirilgan)
  -> har bir backup ishga tushganda (rejali/robot/manual) eski uzoq nusxalar
     ham tozalanadi (prune_remote_backups):
  * s3: bucket ListObjectsV2 bilan ro'yxatlanib, eski backup_*.db[.enc]
    ob'ektlar DELETE orqali o'chiriladi — funksiya kiritilishidan OLDIN
    yuklangan nusxalar ham tozalanadi.
  * telegram: Bot API kanal tarixini ro'yxatlay olmagani uchun har bir
    yuborilgan xabarning message_id si telegram_backup_messages jadvalida
    saqlanadi va eskilari delete_message orqali o'chiriladi (faqat shu
    funksiyadan keyin yuklangan xabarlar — oldingilari kanalda qoladi).

Tiklash (restore):
- list_backup_files() — mavjud backup fayllar ro'yxati (hajmi bilan)
- restore_database() — backup'dan databaseni tiklash: avval joriy DB ning
  xavfsizlik nusxasi olinadi, so'ng backup atomik (os.replace) almashtiriladi,
  natija tekshiriladi va eski ochiq ulanishlar bekor qilinadi.

Eslatma: PostgreSQL rejimi uchun ushbu modul ishlamaydi (loyiha SQLite'ga
asoslangan — upgrade_schema ham faqat SQLite uchun).
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BACKUP_PREFIX = "backup_"
_BACKUP_SUFFIX = ".db"


def _db_file_path() -> Optional[Path]:
    """Asosiy SQLite database fayli yo'lini aniqlash.

    CWD ga nisbatan (SQLITE_DB_PATH) yoki loyiha ildiziga nisbatan qidiriladi.
    """
    from config import BASE_DIR, SQLITE_DB_PATH, USE_POSTGRESQL

    if USE_POSTGRESQL:
        logger.warning("PostgreSQL rejimida avtomatik backup qo'llab-quvvatlanmaydi")
        return None

    candidates = [
        Path(SQLITE_DB_PATH),
        Path(BASE_DIR) / SQLITE_DB_PATH,
        Path(SQLITE_DB_PATH).resolve(),
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand
    # Fayl hali yaratilmagan bo'lsa ham maqsadli yo'lni qaytarish
    return Path(SQLITE_DB_PATH) if Path(SQLITE_DB_PATH).parent.exists() else None


def take_database_backup(db_path=None, backup_dir=None) -> Optional[Path]:
    """SQLite database'dan konsistent zaxira nusxa olish.

    Args:
        db_path: Manba fayl (berilmasa asosiy DB topiladi).
        backup_dir: Saqlanadigan papka (berilmasa BACKUP_DIR).

    Returns:
        Path: Yaratilgan backup fayli; xatolikda None.
    """
    try:
        source = Path(db_path) if db_path else _db_file_path()
        if source is None or not source.exists():
            logger.error(f"Backup uchun database topilmadi: {source}")
            return None

        from config import BACKUP_DIR
        dest_dir = Path(backup_dir) if backup_dir else BACKUP_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Bir soniyada bir nechta backup olinsa (masalan, restore oldidan xavfsizlik
        # nusxasi) fayl nomlari to'qnashmasligi uchun _2, _3... qo'shimchasi qo'yiladi.
        dest = dest_dir / f"{_BACKUP_PREFIX}{timestamp}{_BACKUP_SUFFIX}"
        counter = 2
        while dest.exists():
            dest = dest_dir / f"{_BACKUP_PREFIX}{timestamp}_{counter}{_BACKUP_SUFFIX}"
            counter += 1

        # SQLite online backup — manba ochiq/ishlatilayotgan bo'lsa ham xavfsiz
        src_conn = sqlite3.connect(str(source))
        try:
            dst_conn = sqlite3.connect(str(dest))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()

        # Nusxa haqiqatan ham o'qiladiganligini tekshirish
        check = sqlite3.connect(str(dest))
        try:
            check.execute("PRAGMA integrity_check").fetchone()
        finally:
            check.close()

        logger.info(f"Database backup olindi: {dest} "
                    f"({dest.stat().st_size / 1024:.0f} KB)")
        return dest
    except Exception as e:
        logger.error(f"Database backupda xatolik: {e}", exc_info=True)
        return None


def prune_old_backups(backup_dir=None, keep_days: int = 30) -> int:
    """keep_days dan eski backup fayllarni o'chirish.

    Returns:
        int: O'chirilgan fayllar soni.
    """
    try:
        from config import BACKUP_DIR
        folder = Path(backup_dir) if backup_dir else BACKUP_DIR
        if not folder.exists():
            return 0
        cutoff = datetime.now() - timedelta(days=max(int(keep_days or 30), 0))
        removed = 0
        for f in folder.glob(f"{_BACKUP_PREFIX}*{_BACKUP_SUFFIX}"):
            if not f.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
            except OSError:
                continue
            if mtime < cutoff:
                try:
                    f.unlink()
                    removed += 1
                    logger.info(f"Eski backup o'chirildi: {f.name}")
                except OSError as e:
                    logger.warning(f"Backup o'chirilmadi {f.name}: {e}")
        if removed:
            logger.info(f"{removed} ta eski backup o'chirildi (keep_days={keep_days})")
        return removed
    except Exception as e:
        logger.error(f"Eski backuplarni tozalashda xatolik: {e}")
        return 0


def _target_label(target: str) -> str:
    """Yuklash manzilining qisqa tavsifi (xabar/log uchun)"""
    if target == "telegram":
        return "Telegram kanal"
    if target == "s3":
        cfg = _s3_config()
        return f"S3 ({cfg['s3_bucket']})" if cfg else "S3"
    return target


# =============== Backup run log (SystemLog.details JSON) ===============
# Har bir backup ishga tushirilganda (rejali / bot / web) bitta SystemLog
# yoziladi; `details` ustunida har bir uzoq manzilga yuklash holati struktur
# (JSON) ko'rinishda saqlanadi — web sahifa shu orqali ko'rsatadi.
#
# details sxemasi:
# {
#   "kind": "backup_run",
#   "filename": "backup_20260904_020000.db",
#   "source": "scheduled" | "manual_bot" | "web",
#   "created": true, "error": null | str,
#   "pruned": int, "remote_pruned": {"telegram": int, "s3": int},
#   "encrypted": bool,
#   "targets_configured": bool,
#   "uploads": {"telegram": {"status": "ok"|"failed", "error": null|str}, ...}
# }

def build_backup_log_action(created: Optional[str], pruned: int,
                            uploaded: Optional[Dict[str, bool]] = None,
                            targets_configured: bool = False,
                            remote_pruned: Optional[Dict[str, int]] = None,
                            encrypted: bool = False) -> str:
    """SystemLog action matni — inson o'qiydigan qisqa xulosa"""
    uploaded = uploaded or {}
    remote_pruned = remote_pruned or {}
    parts = [f"{_target_label(t)}: {'yuklandi' if ok else 'yuklanmadi'}"
             for t, ok in uploaded.items()]
    action = (f"Avtomatik backup: {created or 'olinmadi'}"
              f" (pruned={pruned})")
    if parts:
        action += " -> " + ", ".join(parts)
    elif targets_configured:
        action += " -> yuklash amalga oshmadi"
    rparts = [f"{_target_label(t)}: {n} eski o'chirildi"
              for t, n in remote_pruned.items() if n]
    if rparts:
        action += " || Uzoq tozalash: " + ", ".join(rparts)
    if encrypted:
        action += " [shifrlangan]"
    elif targets_configured:
        action += " [shifrlanmagan]"
    return action


def _upload_statuses(uploaded: Optional[Dict[str, bool]],
                     errors: Optional[Dict[str, Optional[str]]]) -> Dict[str, dict]:
    """uploads: {manzil: {status: ok|failed, error: ...}} strukturasi"""
    uploaded = uploaded or {}
    errors = errors or {}
    return {
        t: {"status": "ok" if ok else "failed",
            "error": errors.get(t) or None}
        for t, ok in uploaded.items()
    }


def backup_run_details_json(*, filename: Optional[str], created: bool,
                            pruned: int = 0,
                            remote_pruned: Optional[Dict[str, int]] = None,
                            encrypted: bool = False,
                            uploaded: Optional[Dict[str, bool]] = None,
                            upload_errors: Optional[Dict[str, Optional[str]]] = None,
                            targets_configured: bool = False,
                            source: str = "scheduled",
                            error: Optional[str] = None) -> Optional[str]:
    """SystemLog.details uchun JSON — per-target yuklash holati bilan.

    Returns:
        str|None: JSON matni (details ustuni uchun).
    """
    details = {
        "kind": "backup_run",
        "filename": filename,
        "source": source,
        "created": bool(created),
        "error": error,
        "pruned": int(pruned or 0),
        "remote_pruned": remote_pruned or {},
        "encrypted": bool(encrypted),
        "targets_configured": bool(targets_configured),
        "uploads": _upload_statuses(uploaded, upload_errors),
    }
    return json.dumps(details, ensure_ascii=False, default=str)


def parse_backup_run_details(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """SystemLog.details dagi backup_run JSON'ini o'qish (boshqa yozuvlar uchun None)"""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("kind") != "backup_run":
        return None
    return data


def list_backup_run_logs(db, limit: int = 30) -> List[Dict[str, Any]]:
    """Oxirgi backup run loglari (SystemLog module='backup', details=backup_run JSON).

    Web sahifa har bir backup uchun yuklash holatini (Telegram/S3 ok/failed)
    shu orqali ko'rsatadi. Yangi -> eski tartibda.

    Returns:
        list: [{"filename", "created_at", "source", "encrypted",
                "targets_configured", "uploads": {t: {"status", "error"}}}, ...]
    """
    try:
        from database import models as db_models
        rows = (db.query(db_models.SystemLog)
                .filter(db_models.SystemLog.module == "backup")
                .order_by(db_models.SystemLog.id.desc())
                .limit(max(1, min(int(limit), 200)))
                .all())
        out = []
        for row in rows:
            details = parse_backup_run_details(row.details)
            if details is None:
                continue
            out.append({
                "filename": details.get("filename"),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "action": row.action,
                "source": details.get("source", "scheduled"),
                "created": bool(details.get("created")),
                "error": details.get("error"),
                "encrypted": bool(details.get("encrypted")),
                "targets_configured": bool(details.get("targets_configured")),
                "uploads": details.get("uploads", {}),
            })
        return out
    except Exception as e:
        logger.error(f"Backup run loglarini o'qishda xatolik: {e}")
        return []


async def _notify_backup(result: dict):
    """Adminlarga Telegram xabar + SystemLog'ga yozish + uzoq joyga yuklash (lazy import)"""
    created = result.get("created")
    uploaded: Dict[str, bool] = {}
    upload_errors: Dict[str, Optional[str]] = {}
    encrypted = False
    if created:
        try:
            up = await upload_backup_to_remote(created)
            uploaded = up.get("targets", {})
            upload_errors = up.get("errors", {})
            encrypted = bool(up.get("encrypted"))
        except Exception as e:
            logger.error(f"Backup yuklashda xatolik: {e}")
            upload_errors = {t: str(e) for t in (uploaded or {})}

    targets_configured = bool(_upload_targets())
    remote_pruned = result.get("remote_pruned") or {}

    try:
        from database.session import get_db_session
        from database import crud
        with get_db_session() as db:
            log_action = build_backup_log_action(
                created=created, pruned=result.get("pruned", 0),
                uploaded=uploaded, targets_configured=targets_configured,
                remote_pruned=remote_pruned, encrypted=encrypted)
            details = backup_run_details_json(
                filename=Path(created).name if created else None,
                created=bool(created), pruned=result.get("pruned", 0),
                remote_pruned=remote_pruned, encrypted=encrypted,
                uploaded=uploaded, upload_errors=upload_errors,
                targets_configured=targets_configured,
                source="scheduled",
                error=result.get("error") if not created else None)
            crud.create_system_log(
                db, user_id=0, user_name="Tizim",
                action=log_action,
                module="backup",
                details=details,
            )
    except Exception as e:
        logger.error(f"Backup logini yozishda xatolik: {e}")

    try:
        from utils.notifications import send_notification_to_admins
        if created:
            title = "💾 Avtomatik backup olindi"
            message = (
                f"✅ Database zaxira nusxasi olindi!\n\n"
                f"📁 Fayl: `{created}`\n"
                f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            if uploaded:
                for t, ok in uploaded.items():
                    icon = "✅" if ok else "❌"
                    message += f"\n☁️ {_target_label(t)}ga yuklandi {icon}"
            elif targets_configured:
                message += "\n☁️ Uzoq joyga yuklash amalga oshmadi ⚠️"
            if remote_pruned:
                total = sum(remote_pruned.values())
                if total:
                    message += f"\n♻️ Eski uzoq nusxalar tozalandi: {total} ta"
            if encrypted:
                message += "\n🔐 Nusxa shifrlangan holda yuklandi"
            elif targets_configured:
                message += "\n🔓 Nusxa shifrlanmagan (BACKUP_ENCRYPTION_PASSWORD o'rnatilmagan)"
        else:
            title = "⚠️ Avtomatik backup olinmadi"
            backup_err = result.get("error") or "Noma'lum xatolik"
            message = f"Database backupda xatolik yuz berdi:\n{backup_err}"
        await send_notification_to_admins(title, message, "system_alert")
    except Exception as e:
        logger.error(f"Backup xabarnomasini yuborishda xatolik: {e}")


async def run_database_backup(db_path=None, backup_dir=None,
                              keep_days: Optional[int] = None,
                              notify: bool = True) -> dict:
    """Zaxira nusxa olish + eski nusxalarni tozalash (lokal va uzoq joyda).

    Returns:
        dict: {"created": Path|None, "pruned": int, "error": str|None,
               "remote_pruned": {"telegram": int, "s3": int} | {}}
    """
    created = take_database_backup(db_path=db_path, backup_dir=backup_dir)
    pruned = prune_old_backups(backup_dir=backup_dir, keep_days=keep_days or 30)
    error = None if created else "Database backup olinmadi"

    result = {"created": str(created) if created else None,
              "pruned": pruned, "error": error}
    # Uzoq joydagi eski nusxalarni ham tozalaymiz (BACKUP_REMOTE_KEEP_DAYS;
    # yoqilgan manzillar bo'lmasa bo'sh dict — xato chiqmaydi).
    # Bildirishnoma o'chirilgan bo'lsa ham ishlaydi — uzoq nusxalar to'planib qolmaydi.
    try:
        result["remote_pruned"] = await prune_remote_backups(
            keep_days=keep_days)
    except Exception as e:
        logger.error(f"Uzoq joydagi eski nusxalarni tozalashda xatolik: {e}")
        result["remote_pruned"] = {}
    if notify:
        await _notify_backup(result)
    return result


def list_backup_files(backup_dir=None, limit: Optional[int] = None) -> List[Dict]:
    """Mavjud backup fayllar ro'yxati (yangi -> eski tartibda).

    Har bir yozuv: filename, path, size_bytes, size_mb, created_at.
    """
    try:
        from config import BACKUP_DIR
        folder = Path(backup_dir) if backup_dir else BACKUP_DIR
        files = []
        if folder.exists():
            # Fayl nomida vaqt belgilangan (backup_YYYYMMDD_HHMMSS.db) — nom bo'yicha
            # saralash deterministik; st_mtime esa bir zumda yaratilgan fayllarda
            # bir xil bo'lib qolishi mumkin (tartib buziladi).
            for f in sorted(folder.glob(f"{_BACKUP_PREFIX}*{_BACKUP_SUFFIX}"),
                            key=lambda p: p.name, reverse=True):
                if not f.is_file():
                    continue
                try:
                    size = f.stat().st_size
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                except OSError:
                    continue
                files.append({
                    "filename": f.name,
                    "path": str(f),
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "created_at": mtime.isoformat(),
                })
        return files[:limit] if limit else files
    except Exception as e:
        logger.error(f"Backup ro'yxatini olishda xatolik: {e}")
        return []


def _is_valid_sqlite_backup(path: Path) -> Optional[str]:
    """Fayl haqiqiy/butun SQLite backup ekanligini tekshiradi.

    Returns:
        str|None: Xato xabari yoki None (hammasi joyida).
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                return "Backup fayl buzilgan (integrity check o'tmadi)"
            tables = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()
            if not tables or tables[0] == 0:
                return "Backup faylda jadvallar topilmadi"
        finally:
            conn.close()
        return None
    except Exception as e:
        return f"Backup faylni o'qib bo'lmadi: {e}"


def restore_database(backup_file, create_safety_backup: bool = True) -> Dict:
    """Backup fayldan databaseni tiklash (qaytarib bo'lmaydigan amal!).

    Tartib:
    1. Backup fayl topiladi va butunligi tekshiriladi (integrity + jadvallar).
    2. Xavfsizlik uchun JORIY databasening yangi nusxasi olinadi
       (restore_database_YYYYMMDD_HHMMSS.db) — xato bo'lsa orqaga qaytarish mumkin.
    3. Backup fayl DB o'rniga ATOMIK almashtiriladi (os.replace — ochiq ulanishlar
       eski faylni ko'rishda davom etadi, yangi ulanishlar yangi faylni oladi).
       Manba backup fayl o'z joyida qoladi (o'chirilmaydi).
    4. Tiklangan DB tekshiriladi va eski ochiq ulanishlar bekor qilinadi (engine.dispose)
       — shundan keyingi barcha so'rovlar yangi (tiklangan) faylni o'qiydi.

    Args:
        backup_file: Backup fayl nomi (backups/ papkasida) yoki to'liq yo'l.
        create_safety_backup: Joriy DB dan xavfsizlik nusxasi olinadimi.

    Returns:
        dict: {"success": bool, "error": str|None,
               "safety_backup": str|None, "db_path": str|None}
    """
    try:
        source = Path(backup_file)
        if not source.exists() or not source.is_file():
            # Fayl nomi berilgan bo'lishi mumkin — backups/ papkasidan qidirish
            from config import BACKUP_DIR
            candidate = Path(BACKUP_DIR) / Path(backup_file).name
            if candidate.exists() and candidate.is_file():
                source = candidate
            else:
                return {"success": False, "error": "Backup fayl topilmadi",
                        "safety_backup": None, "db_path": None}

        # Faqat backup nusxa fayllarini tiklashga ruxsat (boshqa fayl emas)
        if not (source.name.startswith(_BACKUP_PREFIX) and source.name.endswith(_BACKUP_SUFFIX)):
            return {"success": False,
                    "error": "Faqat backup_*.db fayllarni tiklash mumkin",
                    "safety_backup": None, "db_path": None}

        db_path = _db_file_path()
        if db_path is None:
            return {"success": False, "error": "Asosiy database topilmadi",
                    "safety_backup": None, "db_path": None}

        # 1. Backup faylni tekshirish
        error = _is_valid_sqlite_backup(source)
        if error:
            return {"success": False, "error": error,
                    "safety_backup": None, "db_path": str(db_path)}

        # 2. Joriy DB ning xavfsizlik nusxasi
        safety = None
        if create_safety_backup:
            safety = take_database_backup()

        # 3. Atomik almashtirish (original backup fayl saqlanib qoladi)
        tmp = db_path.with_name(f".restore_tmp_{datetime.now().strftime('%H%M%S')}")
        try:
            shutil.copy2(str(source), str(tmp))
            os.replace(str(tmp), str(db_path))
        except Exception as e:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise e

        # 4. Tiklangan DB ni tekshirish + eski ulanishlarni bekor qilish
        verify = _is_valid_sqlite_backup(db_path)
        if verify:
            # Xatolik yuz berdi — xavfsizlik nusxasidan qaytarishga urinamiz
            if safety and safety.exists():
                try:
                    shutil.copy2(str(safety), str(tmp))
                    os.replace(str(tmp), str(db_path))
                except Exception:
                    pass
            return {"success": False, "error": f"Tiklash tekshiruvidan o'tmadi: {verify}",
                    "safety_backup": str(safety) if safety else None,
                    "db_path": str(db_path)}

        # Eski ochiq ulanishlar yangi faylga ko'chishi uchun engine'ni yangilash
        try:
            from database.models import engine
            engine.dispose()
        except Exception as e:
            logger.warning(f"Engine dispose qilinmadi: {e}")

        logger.info(f"Database tiklangan: {source.name} -> {db_path}"
                    f" (xavfsizlik nusxasi: {safety.name if safety else '-'})")
        return {"success": True, "error": None,
                "safety_backup": str(safety) if safety else None,
                "db_path": str(db_path)}
    except Exception as e:
        logger.error(f"Database tiklashda xatolik: {e}", exc_info=True)
        return {"success": False, "error": str(e),
                "safety_backup": None, "db_path": None}


def restore_database_from_s3(object_key: str, create_safety_backup: bool = True) -> Dict:
    """S3 bucket'dagi backup'dan databaseni tiklash — yuklab olib, tiklash.

    Bosqichlar:
    1. S3 sozlamalari tekshiriladi (BACKUP_S3_* to'liq bo'lishi kerak).
    2. Ob'ekt kaliti xavfsizligi tekshiriladi: faqat `backup_*.db[.enc]` nomi,
       `s3_prefix` ichida bo'lishi kerak (boshqa fayl tiklanmaydi).
    3. Ob'ekt vaqtinchalik papkaga yuklab olinadi; `.enc` bo'lsa shifr ochiladi.
    4. restore_database() orqali tiklanadi (xavfsizlik nusxasi + atomik almashtirish).

    Returns:
        dict: {"success", "error", "safety_backup", "db_path", "source_key",
               "encrypted", "downloaded"}
    """
    cfg = _s3_config()
    if not cfg:
        return {"success": False,
                "error": "S3 sozlamalari to'liq emas (BACKUP_S3_ENDPOINT/BUCKET/ACCESS_KEY/SECRET_KEY kerak)",
                "safety_backup": None, "db_path": None}

    if not object_key:
        return {"success": False, "error": "S3 ob'ekt kaliti ko'rsatilishi shart",
                "safety_backup": None, "db_path": None}

    name = object_key.rsplit("/", 1)[-1]
    encrypted = name.endswith(_BACKUP_SUFFIX + ".enc")
    # Xavfsizlik: faqat s3_prefix ichidagi backup_*.db[.enc] ob'ektlar
    if not name.startswith(_BACKUP_PREFIX) or \
            not (name.endswith(_BACKUP_SUFFIX) or encrypted):
        return {"success": False,
                "error": "Faqat S3'dagi backup_*.db / backup_*.db.enc ob'ektlarni tiklash mumkin",
                "safety_backup": None, "db_path": None}
    if not object_key.startswith(cfg["s3_prefix"] + "/") and \
            not object_key.startswith(cfg["s3_prefix"]):
        return {"success": False,
                "error": f"Ob'ekt s3_prefix ({cfg['s3_prefix']}) ichida bo'lishi kerak",
                "safety_backup": None, "db_path": None}

    tmp_dir = Path(tempfile.mkdtemp(prefix="cfb_s3restore_"))
    try:
        dl = download_s3_object(cfg, object_key, dest=tmp_dir / name)
        if dl is None:
            return {"success": False, "error": "S3'dan yuklab olish amalga oshmadi",
                    "safety_backup": None, "db_path": None}

        db_file = dl
        if encrypted:
            dec = decrypt_backup_file(
                dl, dest=tmp_dir / name[: -len(".enc")])
            if dec is None:
                return {"success": False,
                        "error": "Shifrlangan nusxani ochib bo'lmadi "
                                 "(BACKUP_ENCRYPTION_PASSWORD to'g'ri o'rnatilganmi?)",
                        "safety_backup": None, "db_path": None}
            db_file = dec

        result = restore_database(str(db_file),
                                  create_safety_backup=create_safety_backup)
        result["source_key"] = object_key
        result["encrypted"] = encrypted
        result["downloaded"] = True
        return result
    except Exception as e:
        logger.error(f"S3'dan tiklashda xatolik: {e}", exc_info=True)
        return {"success": False, "error": str(e),
                "safety_backup": None, "db_path": None}
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def _upload_targets() -> List[str]:
    """BACKUP_UPLOAD dagi yoqilgan VA sozlamasi to'liq bo'lgan manzillar.

    remote: "none" | "telegram" | "s3" | "telegram,s3" (vergul bilan bir nechta).
    Telegram uchun kanal, S3 uchun endpoint+bucket+kalitlar kerak — yo'q bo'lsa
    o'sha manzil tashlab ketiladi.
    """
    try:
        from config import BACKUP_UPLOAD_SETTINGS
    except Exception:
        return []
    remote = str(BACKUP_UPLOAD_SETTINGS.get("remote", "none")).lower()
    wanted = [t for t in (p.strip() for p in remote.split(",")) if t in ("telegram", "s3")]

    out = []
    for t in wanted:
        if t == "telegram":
            if str(BACKUP_UPLOAD_SETTINGS.get("telegram_channel", "")).strip():
                out.append("telegram")
        elif t == "s3":
            if _s3_config():
                out.append("s3")
    return out


def _encryption_password() -> str:
    """BACKUP_ENCRYPTION_PASSWORD — bo'sh bo'lsa shifrlash o'chirilgan"""
    try:
        from config import BACKUP_ENCRYPTION_PASSWORD
        return (BACKUP_ENCRYPTION_PASSWORD or "").strip()
    except Exception:
        return ""


def _encryption_enabled() -> bool:
    return bool(_encryption_password())


_ENCRYPT_MAGIC = b"CFB1"  # fayl formati belgisi (4 bayt)
_ENCRYPT_SALT_LEN = 16
_ENCRYPT_ITERATIONS = 200_000


def _fernet_for(password: str, salt: bytes):
    """Paroldan PBKDF2-SHA256 orqali Fernet kalitini chiqarish"""
    from cryptography.fernet import Fernet
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt,
        _ENCRYPT_ITERATIONS, dklen=32,
    )
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_backup_file(path, password: Optional[str] = None) -> Optional[Path]:
    """Backup faylni shifrlab, yoniga `<nomi>.enc` yaratadi.

    Format: `CFB1` + salt(16) + Fernet token (PBKDF2-200k + AES).
    Manba fayl (lokal nusxa) o'zgarishsiz qoladi — faqat CHIQUVCHI nusxa
    shifrlanadi. Parol berilmasa BACKUP_ENCRYPTION_PASSWORD ishlatiladi.

    Returns:
        Path: Yaratilgan .enc fayl; parol yo'q bo'lsa None.
    """
    password = password if password is not None else _encryption_password()
    if not password:
        return None
    src = Path(path)
    if not src.exists():
        logger.error(f"Shifrlash uchun fayl topilmadi: {path}")
        return None

    salt = os.urandom(_ENCRYPT_SALT_LEN)
    token = _fernet_for(password, salt).encrypt(src.read_bytes())
    out = src.with_name(f"{src.name}.enc")
    out.write_bytes(_ENCRYPT_MAGIC + salt + token)
    logger.info(f"Backup shifrlandi: {src.name} -> {out.name}")
    return out


def decrypt_backup_file(path, password: Optional[str] = None,
                        dest: Optional[Path] = None) -> Optional[Path]:
    """Shifrlangan `.enc` faylni ochish (masalan, uzoq nusxadan tiklashda).

    Args:
        path: `.enc` fayl yo'li.
        password: Parol (berilmasa BACKUP_ENCRYPTION_PASSWORD).
        dest: Ochilgan fayl saqlanadigan joy (default: `.dec.db` yonma-yon).

    Returns:
        Path: Ochilgan fayl; xatolikda (parol noto'g'ri, fayl buzilgan) None.
    """
    password = password if password is not None else _encryption_password()
    if not password:
        logger.error("Shifrni ochish uchun parol kerak (BACKUP_ENCRYPTION_PASSWORD)")
        return None
    src = Path(path)
    if not src.exists():
        logger.error(f"Shifrlangan fayl topilmadi: {path}")
        return None

    data = src.read_bytes()
    if not data.startswith(_ENCRYPT_MAGIC):
        logger.error(f"Fayl shifrlangan formatda emas: {path}")
        return None
    head = len(_ENCRYPT_MAGIC)
    salt = data[head:head + _ENCRYPT_SALT_LEN]
    token = data[head + _ENCRYPT_SALT_LEN:]
    try:
        plain = _fernet_for(password, salt).decrypt(token)
    except Exception as e:
        logger.error(f"Shifr ochilmadi — parol noto'g'ri yoki fayl buzilgan: {e}")
        return None

    out = dest or src.with_name(f"{src.name}.dec.db")
    out.write_bytes(plain)
    logger.info(f"Backup shifri ochildi: {src.name} -> {out.name}")
    return out


# =============== S3 (S3-mos bulut, SigV4, stdlib) ===============
def _s3_config() -> Optional[Dict[str, str]]:
    """S3 sozlamalari — to'liq bo'lmasa None (o'sha manzil o'chirilgan)"""
    try:
        from config import BACKUP_UPLOAD_SETTINGS as S
    except Exception:
        return None
    cfg = {
        "s3_endpoint": str(S.get("s3_endpoint", "") or "").strip(),
        "s3_region": str(S.get("s3_region", "us-east-1") or "us-east-1").strip(),
        "s3_bucket": str(S.get("s3_bucket", "") or "").strip(),
        "s3_access_key": str(S.get("s3_access_key", "") or "").strip(),
        "s3_secret_key": str(S.get("s3_secret_key", "") or "").strip(),
        "s3_prefix": str(S.get("s3_prefix", "backups") or "backups").strip().strip("/"),
    }
    if not (cfg["s3_endpoint"] and cfg["s3_bucket"]
            and cfg["s3_access_key"] and cfg["s3_secret_key"]):
        return None
    return cfg


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _sign_s3_headers(cfg: Dict[str, str], method: str, canonical_uri: str,
                     canonical_query: str, payload_hash: str, amz_date: str,
                     host: str) -> Dict[str, str]:
    """SigV4 imzosi — umumiy qism (PUT / DELETE / GET uchun bir xil)"""
    region = cfg["s3_region"]
    service = "s3"

    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    canonical_request = "\n".join([
        method, canonical_uri, canonical_query,
        canonical_headers, signed_headers, payload_hash,
    ])

    scope = f"{amz_date[:8]}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    k_date = _hmac_sha256(("AWS4" + cfg["s3_secret_key"]).encode("utf-8"), amz_date[:8])
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"),
                         hashlib.sha256).hexdigest()

    return {
        "Host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={cfg['s3_access_key']}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }


def build_s3_put_request(cfg: Dict[str, str], object_key: str, payload: bytes,
                         amz_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """S3'ga SigV4 imzolangan PUT so'rovini tuzadi (yubormaydi).

    Path-style URL: {endpoint}/{bucket}/{key} — AWS S3, MinIO, Wasabi va boshqa
    S3-mos xizmatlar bilan ishlaydi. amz_date berilmasa hozirgi vaqt ishlatiladi
    (testlar deterministik bo'lishi uchun parametr sifatida beriladi).

    Returns:
        dict: {"method", "url", "headers", "body"} yoki None (endpoint noto'g'ri).
    """
    endpoint = cfg["s3_endpoint"].rstrip("/")
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.netloc
    if not host:
        logger.error(f"S3 endpoint noto'g'ri (https://... bo'lishi kerak): {cfg['s3_endpoint']}")
        return None

    # Kalit yo'lini URL-encode qilish (har bir segment alohida)
    encoded_key = "/".join(
        urllib.parse.quote(seg, safe="-_.~") for seg in object_key.split("/")
    )
    canonical_uri = f"/{cfg['s3_bucket']}/{encoded_key}"
    url = f"{endpoint}{canonical_uri}"

    payload_hash = hashlib.sha256(payload).hexdigest()
    amz_date = amz_date or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    headers = _sign_s3_headers(cfg, "PUT", canonical_uri, "",
                               payload_hash, amz_date, host)
    headers["Content-Length"] = str(len(payload))
    return {
        "method": "PUT",
        "url": url,
        "headers": headers,
        "body": payload,
    }


def build_s3_delete_request(cfg: Dict[str, str], object_key: str,
                            amz_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """S3'dan SigV4 imzolangan DELETE so'rovini tuzadi (yubormaydi).

    Uzoq joydagi eski nusxalarni tozalashda ishlatiladi (prune_s3_backups).
    Tanasi yo'q — payload hash bo'sh fayl xeshi.
    """
    endpoint = cfg["s3_endpoint"].rstrip("/")
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.netloc
    if not host:
        logger.error(f"S3 endpoint noto'g'ri: {cfg['s3_endpoint']}")
        return None

    encoded_key = "/".join(
        urllib.parse.quote(seg, safe="-_.~") for seg in object_key.split("/")
    )
    canonical_uri = f"/{cfg['s3_bucket']}/{encoded_key}"
    url = f"{endpoint}{canonical_uri}"

    amz_date = amz_date or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    payload_hash = hashlib.sha256(b"").hexdigest()
    headers = _sign_s3_headers(cfg, "DELETE", canonical_uri, "",
                               payload_hash, amz_date, host)
    return {
        "method": "DELETE",
        "url": url,
        "headers": headers,
        "body": None,
    }


def _s3_canonical_query(params: List[tuple]) -> str:
    """SigV4 kanonik query string: parametrlarni URL-encode qilib, tartiblab birlashtirish"""
    encoded = sorted(
        (urllib.parse.quote(str(k), safe="-_.~"),
         urllib.parse.quote(str(v), safe="-_.~"))
        for k, v in params
    )
    return "&".join(f"{k}={v}" for k, v in encoded)


def build_s3_list_request(cfg: Dict[str, str], prefix: str = "",
                          continuation_token: Optional[str] = None,
                          amz_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """S3 ListObjectsV2 (GET) uchun SigV4 imzolangan so'rov — ob'ektlarni ro'yxatlash.

    Kanonik query: list-type=2&prefix=...&max-keys=1000[&continuation-token=...].
    Eski uzoq nusxalarni topish uchun ishlatiladi (prune_s3_backups).
    """
    endpoint = cfg["s3_endpoint"].rstrip("/")
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.netloc
    if not host:
        logger.error(f"S3 endpoint noto'g'ri: {cfg['s3_endpoint']}")
        return None

    params = [("list-type", "2"), ("prefix", prefix), ("max-keys", "1000")]
    if continuation_token:
        params.append(("continuation-token", continuation_token))
    query = _s3_canonical_query(params)

    canonical_uri = f"/{cfg['s3_bucket']}"
    url = f"{endpoint}{canonical_uri}?{query}"

    amz_date = amz_date or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    payload_hash = hashlib.sha256(b"").hexdigest()
    headers = _sign_s3_headers(cfg, "GET", canonical_uri, query,
                               payload_hash, amz_date, host)
    return {
        "method": "GET",
        "url": url,
        "headers": headers,
        "body": None,
    }


_s3_urlopen = urllib.request.urlopen  # testlarda monkeypatch qilish mumkin


def upload_backup_to_s3(path, object_key: Optional[str] = None,
                        _errors: Optional[Dict[str, str]] = None) -> bool:
    """Backup faylni S3-mos bulutga yuklash (SigV4 imzolangan PUT).

    Ob'ekt yo'li: {s3_prefix}/YYYY/MM/{fayl_nomi} (masalan backups/2026/09/backup_....db)

    Args:
        path: Yuklanadigan fayl.
        object_key: Ixtiyoriy ob'ekt kaliti.
        _errors: Berilsa, xatolik yuz berganda "message" kalitiga sabab yoziladi.

    Returns:
        bool: Yuklangan bo'lsa True.
    """
    def _fail(msg: str) -> bool:
        if _errors is not None:
            _errors["message"] = msg
        logger.warning(msg)
        return False

    cfg = _s3_config()
    if not cfg:
        return _fail("S3 sozlamalari to'liq emas — yuklanmadi "
                     "(BACKUP_S3_ENDPOINT/BUCKET/ACCESS_KEY/SECRET_KEY kerak)")
    file_path = Path(path)
    if not file_path.exists():
        return _fail(f"Yuklanadigan backup fayl topilmadi: {path}")

    data = file_path.read_bytes()
    now = datetime.now()
    key = object_key or f"{cfg['s3_prefix']}/{now:%Y}/{now:%m}/{file_path.name}"
    built = build_s3_put_request(cfg, key, data)
    if built is None:
        return _fail("S3 endpoint noto'g'ri — so'rov tuzilmadi")

    request = urllib.request.Request(
        built["url"], data=built["body"],
        method=built["method"], headers=built["headers"],
    )
    try:
        with _s3_urlopen(request, timeout=60) as resp:  # type: ignore[arg-type]
            if resp.status in (200, 201):
                logger.info(f"Backup S3 ga yuklandi: s3://{cfg['s3_bucket']}/{key}")
                return True
            msg = f"S3 yuklashda kutilmagan javob: {resp.status}"
            if _errors is not None:
                _errors["message"] = msg
            logger.error(msg)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read(500).decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        msg = f"S3 yuklashda xatolik (HTTP {e.code}): {detail}"
        if _errors is not None:
            _errors["message"] = msg
        logger.error(msg)
    except Exception as e:
        if _errors is not None:
            _errors["message"] = str(e)
        logger.error(f"S3 yuklashda xatolik: {e}")
    return False


def _parse_s3_list(data: bytes) -> Dict[str, Any]:
    """S3 ListObjectsV2 XML javobini parsellash.

    Returns:
        dict: {"objects": [{"key", "last_modified"}, ...],
               "is_truncated": bool, "next_token": str|None}
    """
    objects = []
    is_truncated = False
    next_token = None
    try:
        root = ET.fromstring(data)
        for el in root:
            tag = el.tag.rsplit("}", 1)[-1]  # XML namespace'ni tashlab yuborish
            if tag == "Contents":
                key = last = None
                size = 0
                for sub in el:
                    st = sub.tag.rsplit("}", 1)[-1]
                    if st == "Key":
                        key = (sub.text or "").strip()
                    elif st == "LastModified":
                        last = (sub.text or "").strip()
                    elif st == "Size":
                        try:
                            size = int((sub.text or "0").strip() or 0)
                        except ValueError:
                            size = 0
                if key:
                    objects.append({"key": key, "last_modified": last,
                                    "size_bytes": size})
            elif tag == "IsTruncated":
                is_truncated = (el.text or "").strip() == "true"
            elif tag == "NextContinuationToken":
                next_token = (el.text or "").strip() or None
    except ET.ParseError as e:
        logger.error(f"S3 ro'yxat javobini parselashda xatolik: {e}")
    return {"objects": objects, "is_truncated": is_truncated,
            "next_token": next_token}


def _parse_s3_last_modified(value: Optional[str]) -> Optional[datetime]:
    """S3 LastModified (masalan 2026-09-04T12:00:00.000Z) ni datetime ga o'tkazish"""
    if not value:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def build_s3_download_request(cfg: Dict[str, str], object_key: str,
                              amz_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """S3'dan ob'ektni yuklab olish uchun SigV4 imzolangan GET so'rov."""
    endpoint = cfg["s3_endpoint"].rstrip("/")
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.netloc
    if not host:
        logger.error(f"S3 endpoint noto'g'ri: {cfg['s3_endpoint']}")
        return None

    encoded_key = "/".join(
        urllib.parse.quote(seg, safe="-_.~") for seg in object_key.split("/")
    )
    canonical_uri = f"/{cfg['s3_bucket']}/{encoded_key}"
    url = f"{endpoint}{canonical_uri}"

    amz_date = amz_date or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    payload_hash = hashlib.sha256(b"").hexdigest()
    headers = _sign_s3_headers(cfg, "GET", canonical_uri, "",
                               payload_hash, amz_date, host)
    return {
        "method": "GET",
        "url": url,
        "headers": headers,
        "body": None,
    }


def download_s3_object(cfg: Dict[str, str], object_key: str,
                       dest: Optional[Path] = None) -> Optional[Path]:
    """S3'dan ob'ektni yuklab olib, faylga yozadi.

    Returns:
        Path|None: Yuklangan fayl; xatolikda None.
    """
    built = build_s3_download_request(cfg, object_key)
    if built is None:
        return None
    try:
        request = urllib.request.Request(
            built["url"], data=None,
            method=built["method"], headers=built["headers"],
        )
        with _s3_urlopen(request, timeout=60) as resp:  # type: ignore[arg-type]
            if resp.status != 200:
                logger.error(f"S3 yuklab olishda kutilmagan javob: "
                             f"{resp.status} ({object_key})")
                return None
            data = resp.read()
    except urllib.error.HTTPError as e:
        logger.error(f"S3 yuklab olishda xatolik (HTTP {e.code}): {object_key}")
        return None
    except Exception as e:
        logger.error(f"S3 yuklab olishda xatolik: {e}")
        return None

    out = dest or Path(_db_download_path(object_key))
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.write_bytes(data)
    except OSError as e:
        logger.error(f"Yuklab olingan faylni yozishda xatolik: {e}")
        return None
    logger.info(f"S3'dan yuklab olindi: {object_key} ({len(data)} B)")
    return out


def _db_download_path(object_key: str) -> str:
    """Yuklab olingan fayl uchun vaqtinchalik nom (xavfsiz, temp papkada)"""
    name = object_key.rsplit("/", 1)[-1] or "backup_s3.db"
    safe = "".join(c if (c.isalnum() or c in "._-") else "_" for c in name)
    return str(Path(tempfile.gettempdir()) / f"cfb_s3dl_{safe}")


def list_s3_remote_backups(limit: int = 50) -> List[Dict]:
    """S3 bucket'dagi backup ob'ektlari ro'yxati (web/bot uchun).

    Faqat `backup_*.db` / `backup_*.db.enc` nomli ob'ektlar qaytariladi.

    Returns:
        list: [{"key", "name", "size_bytes", "size_mb", "last_modified",
                "encrypted"}, ...]
    """
    cfg = _s3_config()
    if not cfg:
        return []
    objects = list_s3_backup_objects(cfg, prefix=cfg["s3_prefix"])
    out = []
    for obj in objects:
        key = obj.get("key", "")
        name = key.rsplit("/", 1)[-1]
        if not name.startswith(_BACKUP_PREFIX):
            continue
        if not (name.endswith(_BACKUP_SUFFIX)
                or name.endswith(_BACKUP_SUFFIX + ".enc")):
            continue
        size = obj.get("size_bytes") or 0
        out.append({
            "key": key,
            "name": name,
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "last_modified": obj.get("last_modified"),
            "encrypted": name.endswith(_BACKUP_SUFFIX + ".enc"),
        })
    return out[:limit]


def delete_s3_object(cfg: Dict[str, str], object_key: str) -> bool:
    """S3'dan bitta ob'ektni o'chirish (SigV4 DELETE)."""
    built = build_s3_delete_request(cfg, object_key)
    if built is None:
        return False
    try:
        request = urllib.request.Request(
            built["url"], data=None,
            method=built["method"], headers=built["headers"],
        )
        with _s3_urlopen(request, timeout=60) as resp:  # type: ignore[arg-type]
            if resp.status in (200, 204):
                logger.info(f"S3'dan o'chirildi: s3://{cfg['s3_bucket']}/{object_key}")
                return True
            logger.error(f"S3 o'chirishda kutilmagan javob: {resp.status}")
    except urllib.error.HTTPError as e:
        logger.error(f"S3 o'chirishda xatolik (HTTP {e.code}): {object_key}")
    except Exception as e:
        logger.error(f"S3 o'chirishda xatolik: {e}")
    return False


def list_s3_backup_objects(cfg: Dict[str, str], prefix: str = "",
                           max_pages: int = 100) -> List[Dict[str, str]]:
    """S3 bucket'dagi ob'ektlarni ro'yxatlash (ListObjectsV2, sahifalab).

    Returns:
        list: [{"key", "last_modified"}, ...] — faqat o'qish uchun.
    """
    objects: List[Dict[str, str]] = []
    token = None
    for _ in range(max_pages):
        built = build_s3_list_request(cfg, prefix=prefix, continuation_token=token)
        if built is None:
            break
        try:
            request = urllib.request.Request(
                built["url"], data=None,
                method=built["method"], headers=built["headers"],
            )
            with _s3_urlopen(request, timeout=60) as resp:  # type: ignore[arg-type]
                body = resp.read()
        except urllib.error.HTTPError as e:
            logger.error(f"S3 ro'yxatlashda xatolik (HTTP {e.code})")
            break
        except Exception as e:
            logger.error(f"S3 ro'yxatlashda xatolik: {e}")
            break
        parsed = _parse_s3_list(body)
        objects.extend(parsed["objects"])
        if not parsed["is_truncated"] or not parsed["next_token"]:
            break
        token = parsed["next_token"]
    return objects


def prune_s3_backups(keep_days: Optional[int] = None) -> int:
    """S3 bucket'dagi BACKUP_REMOTE_KEEP_DAYS dan eski backup ob'ektlarini o'chirish.

    Bucket ro'yxatlanadi (ListObjectsV2) va nomi backup_*.db / backup_*.db.enc
    bo'lgan, LastModified sanasi eskirgan ob'ektlar DELETE orqali o'chiriladi.
    Shifrlangan (.enc) va oddiy (.db) nusxalar ham tozalanadi.

    Returns:
        int: O'chirilgan ob'ektlar soni.
    """
    cfg = _s3_config()
    if not cfg:
        return 0
    days = max(int(keep_days) if keep_days is not None else _remote_keep_days(), 0)
    if days <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=days)
    prefix = cfg["s3_prefix"]

    removed = 0
    try:
        for obj in list_s3_backup_objects(cfg, prefix=prefix):
            key = obj.get("key", "")
            name = key.rsplit("/", 1)[-1]
            # Faqat bizning backup nomlarimiz (shifrlangan yoki ochiq)
            if not name.startswith(_BACKUP_PREFIX):
                continue
            if not (name.endswith(_BACKUP_SUFFIX)
                    or name.endswith(_BACKUP_SUFFIX + ".enc")):
                continue
            lm = _parse_s3_last_modified(obj.get("last_modified"))
            if lm is not None and lm < cutoff:
                if delete_s3_object(cfg, key):
                    removed += 1
    except Exception as e:
        logger.error(f"S3 eski nusxalarni tozalashda xatolik: {e}", exc_info=True)
    if removed:
        logger.info(f"S3: {removed} ta eski uzoq nusxa o'chirildi (keep_days={days})")
    return removed


async def upload_backup_to_telegram(path, _errors: Optional[Dict[str, str]] = None) -> bool:
    """Backup faylni Telegram kanaliga yuklash (uzoq joyda xavfsiz nusxa).

    telegram_channel (@nomi yoki -100... ID) ko'rsatilgan va BACKUP_UPLOAD da
    "telegram" yoqilgan bo'lishi kerak. Bot instance utils.notifications.bot_instance
    dan olinadi (main.py o'rnatadi).

    Args:
        path: Yuklanadigan fayl.
        _errors: Berilsa, xatolik yuz berganda "message" kalitiga sabab yoziladi
                 (testlar va SystemLog uchun).

    Returns:
        bool: Yuklangan bo'lsa True.
    """
    def _fail(msg: str) -> bool:
        if _errors is not None:
            _errors["message"] = msg
        logger.warning(msg)
        return False

    if "telegram" not in _upload_targets():
        return _fail("Telegram yuklash yoqilmagan (BACKUP_UPLOAD da 'telegram' yo'q)")

    from config import BACKUP_UPLOAD_SETTINGS
    channel = str(BACKUP_UPLOAD_SETTINGS.get("telegram_channel", "")).strip()

    # Lazy import — utils.notifications bilan aylanma importdan qochamiz
    from utils.notifications import bot_instance
    if not bot_instance:
        return _fail("Bot instance o'rnatilmagan — backup yuklanmadi")

    from aiogram.types import FSInputFile
    file_path = Path(path)
    if not file_path.exists():
        return _fail(f"Yuklanadigan backup fayl topilmadi: {path}")

    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > 45:  # Telegram botlar uchun 50MB limit (zaxira bilan 45MB)
        return _fail(f"Backup juda katta ({size_mb:.1f} MB) — Telegram limitidan oshadi")

    caption = (f"💾 Database backup: {file_path.name}\n"
               f"📦 {size_mb:.2f} MB\n"
               f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    try:
        sent = await bot_instance.send_document(
            chat_id=channel,
            document=FSInputFile(str(file_path)),
            caption=caption,
        )
        # Kanal tarixini ro'yxatlab bo'lmagani uchun eski nusxalarni tozalashda
        # ishlatish maqsadida message_id ni saqlaymiz (telegram_backup_messages).
        message_id = getattr(sent, "message_id", None)
        if message_id:
            _record_telegram_message(channel, message_id, file_path.name)
        logger.info(f"Backup Telegram kanalga yuklandi: {file_path.name}"
                    f" (message_id={message_id})")
        return True
    except Exception as e:
        if _errors is not None:
            _errors["message"] = str(e)
        logger.error(f"Backupni Telegram kanalga yuklashda xatolik: {e}")
        return False


def _record_telegram_message(chat_id, message_id, filename: str):
    """Telegram kanalga yuborilgan backup xabari qaydini saqlash"""
    try:
        from database.session import get_db_session
        from database import models as db_models
        with get_db_session() as db:
            db.add(db_models.TelegramBackupMessage(
                chat_id=str(chat_id),
                message_id=int(message_id),
                filename=filename,
            ))
            db.commit()
    except Exception as e:
        logger.warning(f"Telegram backup xabari qaydi saqlanmadi "
                       f"(message_id={message_id}): {e}")


def _chat_id_arg(chat_id: str):
    """Telegram chat_id ni int (raqamli ID) yoki str (@nomi) ko'rinishida qaytaradi"""
    s = str(chat_id).strip()
    try:
        return int(s)
    except ValueError:
        return s


async def _prune_telegram_backups(keep_days: Optional[int] = None) -> int:
    """Telegram kanaldagi eski backup xabarlarini delete_message orqali o'chirish.

    Bot API kanal tarixini ro'yxatlay olmagani uchun saqlangan qaydlar
    (telegram_backup_messages) asosida ishlaydi: sent_at sanasi keep_days dan
    eski bo'lgan xabarlar o'chiriladi va qaydlari tozalanadi.
    """
    days = max(int(keep_days) if keep_days is not None else _remote_keep_days(), 0)
    if days <= 0:
        return 0

    from utils.notifications import bot_instance
    if not bot_instance:
        logger.warning("Bot instance o'rnatilmagan — Telegram uzoq nusxalari tozalanmadi")
        return 0

    cutoff = datetime.utcnow() - timedelta(days=days)
    removed = 0
    try:
        from database.session import get_db_session
        from database import models as db_models
        with get_db_session() as db:
            rows = db.query(db_models.TelegramBackupMessage).filter(
                db_models.TelegramBackupMessage.sent_at < cutoff
            ).all()
            for row in rows:
                try:
                    await bot_instance.delete_message(
                        chat_id=_chat_id_arg(row.chat_id),
                        message_id=row.message_id,
                    )
                    removed += 1
                except Exception as e:
                    msg = str(e).lower()
                    # Xabar/kanal allaqachon o'chirilgan bo'lsa — qaydni tozalaymiz,
                    # aks holda (tarmoq xatosi va h.k.) keyingi siklda qayta urinamiz.
                    gone = ("not found" in msg or "chat not found" in msg
                            or "message to delete not found" in msg)
                    if gone:
                        logger.info(f"Telegram xabari allaqachon yo'q "
                                    f"(chat={row.chat_id}, msg={row.message_id}): {e}")
                    else:
                        logger.warning(f"Telegram xabari o'chirilmadi "
                                       f"(chat={row.chat_id}, msg={row.message_id}): {e}")
                        continue
                db.delete(row)
            db.commit()
    except Exception as e:
        logger.error(f"Telegram uzoq nusxalarini tozalashda xatolik: {e}", exc_info=True)
    if removed:
        logger.info(f"Telegram: {removed} ta eski uzoq nusxa o'chirildi (keep_days={days})")
    return removed


def _remote_keep_days() -> int:
    """BACKUP_REMOTE_KEEP_DAYS (0 bo'lsa uzoq joyda tozalash o'chirilgan)"""
    try:
        from config import BACKUP_UPLOAD_SETTINGS
        return max(int(BACKUP_UPLOAD_SETTINGS.get("remote_keep_days", 0) or 0), 0)
    except Exception:
        return 0


async def prune_remote_backups(keep_days: Optional[int] = None) -> Dict[str, int]:
    """Uzoq joydagi (Telegram kanal / S3 bucket) eski backup nusxalarini tozalash.

    Yoqilgan manzillar uchun ishlaydi; keep_days berilmasa
    BACKUP_REMOTE_KEEP_DAYS (0 bo'lsa o'chirilgan) ishlatiladi.

    Returns:
        dict: {"telegram": int, "s3": int} — har manzilda o'chirilganlar soni.
    """
    targets = _upload_targets()
    if not targets:
        return {}
    days = max(int(keep_days) if keep_days is not None else _remote_keep_days(), 0)
    if days <= 0:
        logger.info("Uzoq joyda tozalash o'chirilgan (BACKUP_REMOTE_KEEP_DAYS=0)")
        return {}

    result: Dict[str, int] = {}
    if "telegram" in targets:
        try:
            result["telegram"] = await _prune_telegram_backups(days)
        except Exception as e:
            logger.error(f"Telegram uzoq nusxalarini tozalashda xatolik: {e}")
    if "s3" in targets:
        try:
            result["s3"] = await asyncio.to_thread(prune_s3_backups, days)
        except Exception as e:
            logger.error(f"S3 uzoq nusxalarini tozalashda xatolik: {e}")
    return result


async def upload_backup_to_remote(path) -> Dict[str, Any]:
    """Backup faylni barcha yoqilgan manzillarga yuklash.

    BACKUP_ENCRYPTION_PASSWORD o'rnatilgan bo'lsa, fayl avval shifrlanadi va
    `.enc` sifatida yuklanadi (vaqtinchalik .enc fayl oxirida o'chiriladi —
    lokal ochiq nusxa saqlanib qoladi).

    Returns:
        dict: {"targets": {"telegram": bool, "s3": bool, ...},
               "errors": {"telegram": str|None, "s3": str|None, ...},
               "encrypted": bool}
    """
    targets = _upload_targets()
    if not targets:
        return {"targets": {}, "errors": {}, "encrypted": False}

    file_path = Path(path)
    if not file_path.exists():
        logger.error(f"Yuklanadigan backup fayl topilmadi: {path}")
        return {"targets": {t: False for t in targets},
                "errors": {t: "Backup fayl topilmadi" for t in targets},
                "encrypted": False}

    enc_path: Optional[Path] = None
    if _encryption_enabled():
        try:
            enc_path = encrypt_backup_file(file_path)
        except Exception as e:
            msg = f"Backupni shifrlashda xatolik — yuklanmadi: {e}"
            logger.error(msg)
            return {"targets": {t: False for t in targets},
                    "errors": {t: msg for t in targets},
                    "encrypted": False}

    upload_path = enc_path if enc_path else file_path
    results: Dict[str, bool] = {}
    errors: Dict[str, Optional[str]] = {}
    try:
        for t in targets:
            box: Dict[str, str] = {}
            try:
                if t == "telegram":
                    results[t] = await upload_backup_to_telegram(
                        str(upload_path), _errors=box)
                elif t == "s3":
                    results[t] = await asyncio.to_thread(
                        upload_backup_to_s3, str(upload_path), None, box)
            except Exception as e:
                msg = f"Backupni {t} ga yuklashda xatolik: {e}"
                logger.error(msg)
                results[t] = False
                box["message"] = msg
            errors[t] = box.get("message")
    finally:
        # Vaqtinchalik shifrlangan nusxani tozalash (lokal ochiq nusxa qoladi)
        if enc_path is not None:
            try:
                if enc_path.exists():
                    enc_path.unlink()
            except OSError as e:
                logger.warning(f"Vaqtinchalik .enc fayl o'chirilmadi: {e}")

    return {"targets": results, "errors": errors, "encrypted": enc_path is not None}


def _parse_time(value: str) -> Optional[tuple]:
    """'HH:MM' formatini (soat, daqiqa) ga o'tkazish"""
    try:
        h, m = str(value or "").strip().split(":")
        return int(h), int(m)
    except (ValueError, TypeError):
        logger.warning(f"BACKUP_SETTINGS['time'] noto'g'ri format: {value}")
        return None


def _schedule_matches(now: datetime, schedule: str) -> bool:
    """daily: har kuni; weekly: dushanba; monthly: oyning 1-kuni"""
    schedule = str(schedule or "daily").lower()
    if schedule == "weekly":
        return now.weekday() == 0
    if schedule == "monthly":
        return now.day == 1
    return True  # daily (default)


async def run_scheduled_backup_if_due(now: Optional[datetime] = None) -> dict:
    """Rejali backup: vaqti kelgan bo'lsa bajaradi (fon vazifasi chaqiradi).

    Args:
        now: Ixtiyoriy vaqt (testlar uchun); berilmasa datetime.now().

    Returns:
        dict: {"due": bool, "created": ..., "pruned": ..., "error": ...}
    """
    try:
        from config import BACKUP_SETTINGS
    except Exception:
        return {"due": False, "created": None, "pruned": 0, "error": None}

    if not BACKUP_SETTINGS.get("enabled", True):
        return {"due": False, "created": None, "pruned": 0, "error": None}

    now = now or datetime.now()
    parsed = _parse_time(BACKUP_SETTINGS.get("time", "02:00"))
    if parsed is None:
        return {"due": False, "created": None, "pruned": 0, "error": None}
    hour, minute = parsed

    if now.hour != hour or now.minute != minute or \
            not _schedule_matches(now, BACKUP_SETTINGS.get("schedule", "daily")):
        return {"due": False, "created": None, "pruned": 0, "error": None}

    logger.info(f"Rejali backup boshlandi ({BACKUP_SETTINGS.get('schedule')} {hour:02d}:{minute:02d})")
    result = await run_database_backup(
        keep_days=BACKUP_SETTINGS.get("keep_days", 30),
        notify=bool(BACKUP_SETTINGS.get("notify_on_backup", True)),
    )
    result["due"] = True
    return result
