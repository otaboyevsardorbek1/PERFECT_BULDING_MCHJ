"""
AVTOMATIK DATABASE BACKUP testlari

utils/backup.py — SQLite online backup API si orqali konsistent nusxa olinadi,
eski nusxalar keep_days bo'yicha tozalanadi, BACKUP_TIME da fon vazifasi ishga
tushiradi. Shuningdek: ro'yxat, tiklash, Telegram/S3 ga yuklash va chiqishdan
oldin shifrlash (PBKDF2 + Fernet).
"""
import hashlib
import io
import os
import sqlite3
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from utils import backup as backup_mod


@pytest.fixture
def src_db(tmp_path):
    """Kichik haqiqiy SQLite fayl — ma'lumot bilan"""
    path = tmp_path / "construction.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO products (name) VALUES ('Sement')")
    conn.execute("INSERT INTO products (name) VALUES ('G''ish')")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def backup_env(monkeypatch, src_db, tmp_path):
    """Backup papkasi va DB yo'lini test papkasiga yo'naltiradi"""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    monkeypatch.setattr("config.BACKUP_DIR", backup_dir)
    monkeypatch.setattr("config.SQLITE_DB_PATH", str(src_db))
    monkeypatch.setattr("config.USE_POSTGRESQL", False)
    return {"backup_dir": backup_dir, "src_db": src_db}


def _set_settings(monkeypatch, **kw):
    from config import BACKUP_SETTINGS
    base = {"enabled": True, "schedule": "daily", "time": "02:00",
            "keep_days": 30, "notify_on_backup": False}
    base.update(kw)
    for k, v in base.items():
        monkeypatch.setitem(BACKUP_SETTINGS, k, v)


class TestTakeBackup:
    def test_creates_consistent_copy(self, backup_env):
        src = backup_env["src_db"]
        dest = backup_mod.take_database_backup()
        assert dest is not None
        assert dest.name.startswith("backup_")
        assert dest.name.endswith(".db")
        assert dest.exists() and dest.stat().st_size > 0

        # Nusxa ochilib o'qiladi va ma'lumot bor
        conn = sqlite3.connect(str(dest))
        rows = conn.execute("SELECT name FROM products ORDER BY id").fetchall()
        assert [r[0] for r in rows] == ["Sement", "G'ish"]
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        assert ok == "ok"

    def test_backup_works_while_source_open(self, backup_env):
        """Manba boshqa ulanish ochiq bo'lsa ham konsistent nusxa olinadi"""
        src = backup_env["src_db"]
        live = sqlite3.connect(str(src))
        try:
            live.execute("BEGIN")
            live.execute("INSERT INTO products (name) VALUES ('Yangi')")
            dest = backup_mod.take_database_backup()
            # Backup oldingi holatni saqlaydi (transaction commit qilinmagan)
            conn = sqlite3.connect(str(dest))
            n = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            conn.close()
            assert dest is not None
            assert n == 2  # commit qilinmagan yozuv kirmaydi
        finally:
            live.rollback()
            live.close()

    def test_missing_source_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.SQLITE_DB_PATH", str(tmp_path / "yoq.db"))
        monkeypatch.setattr("config.USE_POSTGRESQL", False)
        assert backup_mod.take_database_backup() is None


class TestPrune:
    def _make_backup(self, folder, name, age_days):
        f = folder / f"backup_{name}.db"
        f.write_bytes(b"data")
        old = datetime.now() - timedelta(days=age_days)
        os.utime(f, (old.timestamp(), old.timestamp()))
        return f

    def test_removes_old_keeps_recent(self, backup_env, tmp_path):
        folder = backup_env["backup_dir"]
        old1 = self._make_backup(folder, "20260101_000000", 40)
        old2 = self._make_backup(folder, "20260110_000000", 35)
        new = self._make_backup(folder, "20260220_000000", 2)

        removed = backup_mod.prune_old_backups(keep_days=30)
        assert removed == 2
        assert not old1.exists() and not old2.exists()
        assert new.exists()

    def test_ignores_unrelated_files(self, backup_env):
        folder = backup_env["backup_dir"]
        (folder / "notes.txt").write_text("muhim emas")
        (folder / "backup_20260101_000000.db").write_bytes(b"x")
        old = datetime.now() - timedelta(days=90)
        os.utime(folder / "backup_20260101_000000.db",
                 (old.timestamp(), old.timestamp()))

        backup_mod.prune_old_backups(keep_days=30)
        assert (folder / "notes.txt").exists()  # boshqa faylga tegmaydi


class TestScheduler:
    async def test_disabled_returns_not_due(self, monkeypatch, backup_env):
        _set_settings(monkeypatch, enabled=False)
        result = await backup_mod.run_scheduled_backup_if_due(
            now=datetime(2026, 1, 1, 2, 0))
        assert result["due"] is False
        assert not list(backup_env["backup_dir"].glob("backup_*.db"))

    async def test_not_due_time(self, monkeypatch, backup_env):
        _set_settings(monkeypatch)
        result = await backup_mod.run_scheduled_backup_if_due(
            now=datetime(2026, 1, 1, 10, 30))
        assert result["due"] is False
        assert not list(backup_env["backup_dir"].glob("backup_*.db"))

    async def test_due_runs_backup(self, monkeypatch, backup_env):
        _set_settings(monkeypatch, keep_days=30)
        result = await backup_mod.run_scheduled_backup_if_due(
            now=datetime(2026, 1, 1, 2, 0))
        assert result["due"] is True
        assert result["created"] is not None
        assert result["error"] is None
        files = list(backup_env["backup_dir"].glob("backup_*.db"))
        assert len(files) == 1

    async def test_weekly_only_on_monday(self, monkeypatch, backup_env):
        _set_settings(monkeypatch, schedule="weekly")
        # Seshanba (weekday=1) — ishlamaydi
        r1 = await backup_mod.run_scheduled_backup_if_due(
            now=datetime(2026, 1, 6, 2, 0))
        assert r1["due"] is False
        # Dushanba (weekday=0) — ishlaydi
        r2 = await backup_mod.run_scheduled_backup_if_due(
            now=datetime(2026, 1, 5, 2, 0))
        assert r2["due"] is True and r2["created"] is not None

    async def test_due_prunes_old_and_keeps_new(self, monkeypatch, backup_env):
        folder = backup_env["backup_dir"]
        # 40 kunlik eski nusxa — o'chishi kerak
        old_f = folder / "backup_20250101_000000.db"
        old_f.write_bytes(b"old")
        old = datetime.now() - timedelta(days=40)
        os.utime(old_f, (old.timestamp(), old.timestamp()))

        _set_settings(monkeypatch, keep_days=30)
        result = await backup_mod.run_scheduled_backup_if_due(
            now=datetime(2026, 1, 1, 2, 0))
        assert result["pruned"] == 1
        assert result["created"] is not None
        assert not old_f.exists()


class TestListBackups:
    def test_empty_dir(self, backup_env):
        assert backup_mod.list_backup_files() == []

    def test_lists_files_sorted_with_sizes(self, backup_env):
        folder = backup_env["backup_dir"]
        f1 = folder / "backup_20260101_000000.db"
        f1.write_bytes(b"x" * 2048)
        f2 = folder / "backup_20260102_000000.db"
        f2.write_bytes(b"y" * 1024)
        (folder / "notes.txt").write_text("tegishli emas")

        files = backup_mod.list_backup_files()
        # Yangi -> eski tartib, boshqa fayllar kirmaydi
        assert [f["filename"] for f in files] == ["backup_20260102_000000.db",
                                                   "backup_20260101_000000.db"]
        assert files[0]["size_bytes"] == 1024
        assert files[1]["size_mb"] == round(2048 / (1024 * 1024), 2)
        assert files[0]["created_at"]  # ISO sana

    def test_limit(self, backup_env):
        folder = backup_env["backup_dir"]
        for name in ["backup_20260101_000000.db", "backup_20260102_000000.db",
                     "backup_20260103_000000.db"]:
            (folder / name).write_bytes(b"d")
        files = backup_mod.list_backup_files(limit=2)
        assert len(files) == 2
        assert files[0]["filename"].endswith("20260103_000000.db")


class TestRestore:
    def _backup(self, backup_env):
        """src_db ning hozirgi holatini nusxalaydi va Path qaytaradi"""
        dest = backup_mod.take_database_backup()
        assert dest is not None
        return dest

    def _row_names(self, path):
        conn = sqlite3.connect(str(path))
        try:
            return [r[0] for r in conn.execute("SELECT name FROM products ORDER BY id")]
        finally:
            conn.close()

    def test_restore_rolls_back_to_backup_state(self, backup_env):
        src = backup_env["src_db"]
        # Backup: 2 ta yozuv holatida
        backup = self._backup(backup_env)

        # Keyin DB ga yangi yozuv qo'shiladi ("buzilgan" holat)
        conn = sqlite3.connect(str(src))
        conn.execute("INSERT INTO products (name) VALUES ('Noto''g''ri yozuv')")
        conn.commit()
        conn.close()
        assert len(self._row_names(src)) == 3

        result = backup_mod.restore_database(backup.name)
        assert result["success"] is True
        assert result["error"] is None
        # DB backup holatiga qaytdi
        assert self._row_names(src) == ["Sement", "G'ish"]
        # Xavfsizlik nusxasi ham olindi
        assert result["safety_backup"] is not None
        assert Path(result["safety_backup"]).exists()
        # Xavfsizlik nusxasida yangi yozuv bor (orqaga qaytarish mumkin)
        assert self._row_names(result["safety_backup"]) == ["Sement", "G'ish", "Noto'g'ri yozuv"]
        # Asl backup fayl o'chirilmagan (tarixda qoladi)
        assert (backup_env["backup_dir"] / backup.name).exists()

    def test_restore_missing_file(self, backup_env):
        result = backup_mod.restore_database("backup_19990101_000000.db")
        assert result["success"] is False
        assert "topilmadi" in (result["error"] or "")

    def test_restore_corrupted_file(self, backup_env):
        folder = backup_env["backup_dir"]
        bad = folder / "backup_20260101_000000.db"
        bad.write_bytes(b"bu sqlite emas")

        result = backup_mod.restore_database(bad.name)
        assert result["success"] is False
        assert result["error"] is not None
        # DB o'zgarmagan
        assert self._row_names(backup_env["src_db"]) == ["Sement", "G'ish"]

    def test_restore_rejects_unrelated_filename(self, backup_env, tmp_path):
        # backup_ prefiksiga ega bo'lmagan faylni tiklash mumkin emas
        evil = tmp_path / "notes.txt"
        evil.write_text("sqlite emas")
        result = backup_mod.restore_database(str(evil))
        assert result["success"] is False
        assert result["error"] is not None


class TestUpload:
    def _enable_upload(self, monkeypatch, channel="-100111222333"):
        import config as config_mod
        monkeypatch.setattr(config_mod, "BACKUP_UPLOAD_SETTINGS", {
            "remote": "telegram",
            "telegram_channel": channel,
        })

    async def test_disabled_returns_false(self, backup_env):
        # remote sozlanmagan bo'lsa hech narsa yuborilmaydi
        result = await backup_mod.upload_backup_to_telegram(
            str(backup_env["src_db"]))
        assert result is False

    async def test_enabled_sends_document(self, monkeypatch, backup_env):
        self._enable_upload(monkeypatch)

        class _FakeBot:
            def __init__(self):
                self.sent = []

            async def send_document(self, chat_id, document, caption=None):
                self.sent.append((chat_id, document.filename, caption))
                return True

        fake = _FakeBot()
        import utils.notifications as notif_mod
        monkeypatch.setattr(notif_mod, "bot_instance", fake)

        ok = await backup_mod.upload_backup_to_telegram(
            str(backup_env["src_db"]))
        assert ok is True
        assert len(fake.sent) == 1
        chat_id, filename, caption = fake.sent[0]
        assert chat_id == "-100111222333"
        assert filename == backup_env["src_db"].name
        assert "backup" in caption.lower() or "Database" in caption

    async def test_enabled_without_channel_skips(self, monkeypatch, backup_env):
        self._enable_upload(monkeypatch, channel="")
        import utils.notifications as notif_mod

        class _FakeBot:
            async def send_document(self, chat_id, document, caption=None):
                raise AssertionError("kanal yo'q bo'lsa yubormaslik kerak")

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        ok = await backup_mod.upload_backup_to_telegram(
            str(backup_env["src_db"]))
        assert ok is False


def _set_upload(monkeypatch, remote="s3", channel="-100111222333", s3_keys=True):
    """BACKUP_UPLOAD_SETTINGS ni test holatiga o'rnatish"""
    import config as config_mod
    monkeypatch.setattr(config_mod, "BACKUP_UPLOAD_SETTINGS", {
        "remote": remote,
        "telegram_channel": channel,
        "s3_endpoint": "https://s3.example.test",
        "s3_region": "us-east-1",
        "s3_bucket": "backup-test",
        "s3_access_key": "AKIDEXAMPLE",
        "s3_secret_key": "s3cr3tsecretkey" if s3_keys else "",
        "s3_prefix": "backups",
    })


def _set_password(monkeypatch, value="parol-123"):
    import config as config_mod
    monkeypatch.setattr(config_mod, "BACKUP_ENCRYPTION_PASSWORD", value)


class TestEncrypt:
    def test_disabled_without_password(self, backup_env, monkeypatch):
        _set_password(monkeypatch, "")
        result = backup_mod.encrypt_backup_file(backup_env["src_db"])
        assert result is None
        assert not Path(str(backup_env["src_db"]) + ".enc").exists()

    def test_encrypt_decrypt_roundtrip(self, backup_env, monkeypatch):
        _set_password(monkeypatch, "parol-123")
        src = backup_env["src_db"]
        enc = backup_mod.encrypt_backup_file(src)
        assert enc is not None
        assert enc.name == src.name + ".enc"
        assert enc.exists()

        # Format: magic + salt + token; ochiq matn ciphertextda ko'rinmaydi
        raw = enc.read_bytes()
        assert raw.startswith(backup_mod._ENCRYPT_MAGIC)
        assert b"Sement" not in raw

        # Ochish — asl fayl bilan bir xil
        dec = backup_mod.decrypt_backup_file(enc)
        assert dec is not None
        assert dec.read_bytes() == src.read_bytes()

        # Noto'g'ri parol -> ochilmaydi
        bad = backup_mod.decrypt_backup_file(enc, password="noto'g'ri")
        assert bad is None

    async def test_telegram_gets_encrypted_file(self, backup_env, monkeypatch):
        """Orchestrator: telegram + parol -> kanalga .enc fayl yuboriladi"""
        _set_password(monkeypatch, "parol-123")
        _set_upload(monkeypatch, remote="telegram")
        import utils.notifications as notif_mod

        class _FakeBot:
            def __init__(self):
                self.sent = []

            async def send_document(self, chat_id, document, caption=None):
                self.sent.append((chat_id, document.filename, caption))
                return True

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        res = await backup_mod.upload_backup_to_remote(backup_env["src_db"])
        assert res["encrypted"] is True
        assert res["targets"]["telegram"] is True
        fake = notif_mod.bot_instance
        assert fake.sent[0][1].endswith(".enc")
        # Vaqtinchalik .enc tozalandi
        assert not Path(str(backup_env["src_db"]) + ".enc").exists()


class TestS3:
    def test_targets_detection(self, monkeypatch, backup_env):
        # O'chirilgan
        _set_upload(monkeypatch, remote="none")
        assert backup_mod._upload_targets() == []
        # Telegram — kanalsiz tushib ketadi
        _set_upload(monkeypatch, remote="telegram,s3", channel="")
        targets = backup_mod._upload_targets()
        assert "telegram" not in targets
        assert "s3" in targets
        # Ikkalasi ham
        _set_upload(monkeypatch, remote="telegram,s3", channel="-100111")
        assert backup_mod._upload_targets() == ["telegram", "s3"]
        # S3 kalitlarsiz
        _set_upload(monkeypatch, remote="s3", s3_keys=False)
        assert backup_mod._upload_targets() == []

    def test_build_s3_request_signature(self, backup_env):
        cfg = {
            "s3_endpoint": "https://s3.amazonaws.com", "s3_region": "us-east-1",
            "s3_bucket": "my-bucket", "s3_access_key": "AKIDEXAMPLE",
            "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "s3_prefix": "backups",
        }
        built = backup_mod.build_s3_put_request(
            cfg, "backups/2026/09/backup_20260901_020000.db",
            b"hello", amz_date="20260901T020000Z")
        assert built is not None
        assert built["method"] == "PUT"
        assert built["url"] == "https://s3.amazonaws.com/my-bucket/backups/2026/09/backup_20260901_020000.db"
        auth = built["headers"]["Authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20260901/us-east-1/s3/aws4_request")
        assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth
        signature = auth.split("Signature=")[1]
        assert len(signature) == 64  # hex sha256
        assert built["headers"]["x-amz-date"] == "20260901T020000Z"
        assert built["headers"]["x-amz-content-sha256"] == \
            hashlib.sha256(b"hello").hexdigest()

    def test_upload_success(self, monkeypatch, backup_env):
        _set_upload(monkeypatch, remote="s3")
        captured = {}

        class _FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_open(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = req.headers
            captured["data"] = req.data
            return _FakeResp()

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fake_open)
        ok = backup_mod.upload_backup_to_s3(backup_env["src_db"])
        assert ok is True
        assert captured["url"].startswith(
            "https://s3.example.test/backup-test/backups/")
        assert captured["url"].endswith(backup_env["src_db"].name)
        assert "Authorization" in captured["headers"]
        assert captured["data"] == backup_env["src_db"].read_bytes()

    def test_upload_http_error_false(self, monkeypatch, backup_env):
        _set_upload(monkeypatch, remote="s3")

        def fake_open(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 403, "Forbidden", {},
                io.BytesIO(b"<Error><Code>AccessDenied</Code></Error>"))

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fake_open)
        assert backup_mod.upload_backup_to_s3(backup_env["src_db"]) is False

    def test_upload_missing_config_false(self, monkeypatch, backup_env):
        _set_upload(monkeypatch, remote="s3", s3_keys=False)
        assert backup_mod.upload_backup_to_s3(backup_env["src_db"]) is False

    async def test_upload_to_remote_encrypts_and_cleans(self, monkeypatch, backup_env):
        """Orchestrator: s3 + parol -> .enc yuklanadi, vaqtinchalik fayl tozalanadi"""
        _set_upload(monkeypatch, remote="s3")
        _set_password(monkeypatch, "parol-123")
        captured = {}

        class _FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_open(req, timeout=None):
            captured["url"] = req.full_url
            return _FakeResp()

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fake_open)
        res = await backup_mod.upload_backup_to_remote(backup_env["src_db"])
        assert res["encrypted"] is True
        assert res["targets"]["s3"] is True
        # Yuklangan ob'ekt .enc bilan tugaydi
        assert captured["url"].endswith(backup_env["src_db"].name + ".enc")
        # Vaqtinchalik .enc lokalda qolmadi; ochiq nusxa qoldi
        assert not Path(str(backup_env["src_db"]) + ".enc").exists()
        assert backup_env["src_db"].exists()


class TestNotify:
    async def test_notify_sends_and_logs(self, monkeypatch, db_session):
        import database.crud as crud_mod
        import database.session as session_mod
        import utils.notifications as notif_mod

        class _Ctx:
            def __enter__(self):
                return db_session

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(session_mod, "get_db_session", lambda: _Ctx())
        logged = []
        monkeypatch.setattr(crud_mod, "create_system_log",
                            lambda db, **kw: logged.append(kw))
        sent = []
        async def fake_send(title, message, ntype):
            sent.append((title, message, ntype))
            return True
        monkeypatch.setattr(notif_mod, "send_notification_to_admins", fake_send)

        await backup_mod._notify_backup(
            {"created": "/tmp/backups/backup_x.db", "pruned": 1, "error": None})

        assert len(sent) == 1
        assert "Avtomatik backup olindi" in sent[0][0]
        assert "backup_x.db" in sent[0][1]
        assert len(logged) == 1
        assert logged[0]["module"] == "backup"


class _CtxSession:
    """get_db_session ni test sessiyasiga yo'naltiruvchi kontekst"""
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *a):
        return False


def _patch_db_session(monkeypatch, db_session):
    import database.session as session_mod
    monkeypatch.setattr(session_mod, "get_db_session", lambda: _CtxSession(db_session))


def _tg_settings(monkeypatch, remote_keep_days=30):
    """Telegram uzoq joy sozlamalari (retention bilan)"""
    _set_upload(monkeypatch, remote="telegram")
    import config as config_mod
    config_mod.BACKUP_UPLOAD_SETTINGS["remote_keep_days"] = remote_keep_days


class TestS3DeleteSigner:
    def test_delete_request_signature(self):
        cfg = {
            "s3_endpoint": "https://s3.amazonaws.com", "s3_region": "us-east-1",
            "s3_bucket": "my-bucket", "s3_access_key": "AKIDEXAMPLE",
            "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "s3_prefix": "backups",
        }
        built = backup_mod.build_s3_delete_request(
            cfg, "backups/2026/09/backup_20260101_020000.db",
            amz_date="20260901T020000Z")
        assert built is not None
        assert built["method"] == "DELETE"
        assert built["url"] == "https://s3.amazonaws.com/my-bucket/backups/2026/09/backup_20260101_020000.db"
        auth = built["headers"]["Authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20260901/us-east-1/s3/aws4_request")
        # Bo'sh payload xeshi (tana yo'q)
        assert built["headers"]["x-amz-content-sha256"] == hashlib.sha256(b"").hexdigest()
        assert "Signature=" in auth

    def test_list_request_query_and_signature(self):
        cfg = {
            "s3_endpoint": "https://s3.amazonaws.com", "s3_region": "us-east-1",
            "s3_bucket": "my-bucket", "s3_access_key": "AKIDEXAMPLE",
            "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "s3_prefix": "backups",
        }
        built = backup_mod.build_s3_list_request(
            cfg, prefix="backups", continuation_token="TOK123",
            amz_date="20260901T020000Z")
        assert built is not None
        assert built["method"] == "GET"
        assert built["url"].startswith("https://s3.amazonaws.com/my-bucket?")
        # Kanonik tartiblangan query parametrlari
        assert "list-type=2" in built["url"]
        assert "prefix=backups" in built["url"]
        assert "max-keys=1000" in built["url"]
        assert "continuation-token=TOK123" in built["url"]
        auth = built["headers"]["Authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20260901/us-east-1/s3/aws4_request")
        assert "Signature=" in auth

    def test_parse_s3_list_xml(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>my-bucket</Name>
  <Prefix>backups/</Prefix>
  <KeyCount>2</KeyCount>
  <MaxKeys>1000</MaxKeys>
  <IsTruncated>true</IsTruncated>
  <Contents><Key>backups/2026/09/backup_20260101_020000.db</Key>
    <LastModified>2026-01-01T02:00:00.000Z</LastModified>
    <Size>10</Size></Contents>
  <Contents><Key>backups/2026/09/backup_20260102_020000.db.enc</Key>
    <LastModified>2026-01-02T02:00:00.000Z</LastModified>
    <Size>11</Size></Contents>
  <NextContinuationToken>NEXT123</NextContinuationToken>
</ListBucketResult>"""
        parsed = backup_mod._parse_s3_list(xml)
        assert parsed["is_truncated"] is True
        assert parsed["next_token"] == "NEXT123"
        assert len(parsed["objects"]) == 2
        assert parsed["objects"][0]["key"].endswith(".db")
        assert parsed["objects"][1]["key"].endswith(".db.enc")

    def test_parse_last_modified(self):
        assert backup_mod._parse_s3_last_modified("2026-01-01T02:00:00.000Z") == \
            datetime(2026, 1, 1, 2, 0, 0)
        assert backup_mod._parse_s3_last_modified("2026-01-01T02:00:00Z") == \
            datetime(2026, 1, 1, 2, 0, 0)
        assert backup_mod._parse_s3_last_modified("buzilgan") is None
        assert backup_mod._parse_s3_last_modified(None) is None


class TestS3Prune:
    def _settings(self, monkeypatch):
        _set_upload(monkeypatch, remote="s3")
        import config as config_mod
        config_mod.BACKUP_UPLOAD_SETTINGS["remote_keep_days"] = 30
        return config_mod.BACKUP_UPLOAD_SETTINGS

    def _fmt(self, dt):
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def test_removes_old_keeps_recent_and_unrelated(self, monkeypatch, backup_env):
        self._settings(monkeypatch)
        old1 = datetime.utcnow() - timedelta(days=40)
        old2 = datetime.utcnow() - timedelta(days=45)
        recent = datetime.utcnow() - timedelta(days=1)

        xml = (f"<?xml version='1.0'?><ListBucketResult xmlns='http://s3.amazonaws.com/doc/2006-03-01/'>"
               f"<IsTruncated>false</IsTruncated>"
               f"<Contents><Key>backups/2026/09/backup_{old1:%Y%m%d}_020000.db</Key>"
               f"<LastModified>{self._fmt(old1)}</LastModified></Contents>"
               f"<Contents><Key>backups/2026/08/backup_{old2:%Y%m%d}_020000.db.enc</Key>"
               f"<LastModified>{self._fmt(old2)}</LastModified></Contents>"
               f"<Contents><Key>backups/2026/09/backup_{recent:%Y%m%d}_020000.db</Key>"
               f"<LastModified>{self._fmt(recent)}</LastModified></Contents>"
               f"<Contents><Key>backups/2026/09/notes.txt</Key>"
               f"<LastModified>{self._fmt(old1)}</LastModified></Contents>"
               f"</ListBucketResult>")

        deleted = []

        class _FakeListResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return xml.encode("utf-8")

        class _FakeDelResp:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b""

        def fake_open(req, timeout=None):
            if req.get_method() == "GET":
                return _FakeListResp()
            deleted.append(req.full_url)
            return _FakeDelResp()

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fake_open)
        removed = backup_mod.prune_s3_backups(keep_days=30)
        assert removed == 2
        assert len(deleted) == 2
        # Faqat eski backup fayllar o'chiriladi — .enc ham, yangisi ham qoladi
        assert any(u.endswith(f"backup_{old1:%Y%m%d}_020000.db") for u in deleted)
        assert any(u.endswith(f"backup_{old2:%Y%m%d}_020000.db.enc") for u in deleted)
        assert not any("notes.txt" in u for u in deleted)
        assert not any(f"backup_{recent:%Y%m%d}_020000.db" in u for u in deleted)

    def test_no_config_or_disabled_returns_zero(self, monkeypatch, backup_env):
        _set_upload(monkeypatch, remote="s3", s3_keys=False)
        assert backup_mod.prune_s3_backups(keep_days=30) == 0
        self._settings(monkeypatch)
        # remote_keep_days = 0 -> o'chirilgan
        assert backup_mod.prune_s3_backups(keep_days=0) == 0


class TestTelegramPrune:
    def _row(self, db_session, message_id, age_days, chat="-100111222333"):
        from database import models as db_models
        row = db_models.TelegramBackupMessage(
            chat_id=chat,
            message_id=message_id,
            filename=f"backup_{message_id}.db",
            sent_at=datetime.utcnow() - timedelta(days=age_days),
        )
        db_session.add(row)
        db_session.commit()
        return row.id

    async def test_upload_records_message(self, monkeypatch, backup_env, db_session):
        _tg_settings(monkeypatch)
        _patch_db_session(monkeypatch, db_session)
        import utils.notifications as notif_mod

        class _FakeBot:
            async def send_document(self, chat_id, document, caption=None):
                return type("Msg", (), {"message_id": 42})()

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        ok = await backup_mod.upload_backup_to_telegram(str(backup_env["src_db"]))
        assert ok is True
        from database import models as db_models
        rows = db_session.query(db_models.TelegramBackupMessage).all()
        assert len(rows) == 1
        assert rows[0].message_id == 42
        assert rows[0].chat_id == "-100111222333"
        assert rows[0].filename == backup_env["src_db"].name

    async def test_prune_deletes_old_keeps_new(self, monkeypatch, backup_env, db_session):
        _tg_settings(monkeypatch)
        _patch_db_session(monkeypatch, db_session)
        import utils.notifications as notif_mod
        self._row(db_session, 101, 40)  # eski (message_id=101)
        self._row(db_session, 202, 1)   # yangi (message_id=202)

        deleted = []

        class _FakeBot:
            async def delete_message(self, chat_id, message_id):
                deleted.append((chat_id, message_id))

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        result = await backup_mod.prune_remote_backups()
        assert result == {"telegram": 1}
        assert deleted == [(-100111222333, 101)]
        from database import models as db_models
        remaining = [r.message_id for r in
                     db_session.query(db_models.TelegramBackupMessage).all()]
        assert remaining == [202]

    async def test_prune_not_found_clears_row(self, monkeypatch, backup_env, db_session):
        _tg_settings(monkeypatch)
        _patch_db_session(monkeypatch, db_session)
        import utils.notifications as notif_mod
        old_id = self._row(db_session, 301, 40)

        class _FakeBot:
            async def delete_message(self, chat_id, message_id):
                raise Exception("Bad Request: message to delete not found")

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        result = await backup_mod.prune_remote_backups()
        # Xabar allaqachon yo'q — qayd tozalanadi (o'chirish soniga kirmaydi)
        assert result == {"telegram": 0}
        from database import models as db_models
        assert db_session.query(db_models.TelegramBackupMessage).filter(
            db_models.TelegramBackupMessage.id == old_id).first() is None

    async def test_prune_error_keeps_row_for_retry(self, monkeypatch, backup_env, db_session):
        _tg_settings(monkeypatch)
        _patch_db_session(monkeypatch, db_session)
        import utils.notifications as notif_mod
        old_id = self._row(db_session, 401, 40)

        class _FakeBot:
            async def delete_message(self, chat_id, message_id):
                raise Exception("flood control")

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        result = await backup_mod.prune_remote_backups()
        assert result == {"telegram": 0}
        from database import models as db_models
        # Keyingi siklda qayta urinish uchun qayd qoladi
        assert db_session.query(db_models.TelegramBackupMessage).filter(
            db_models.TelegramBackupMessage.id == old_id).first() is not None

    async def test_no_bot_instance_returns_zero(self, monkeypatch, backup_env, db_session):
        _tg_settings(monkeypatch)
        _patch_db_session(monkeypatch, db_session)
        import utils.notifications as notif_mod
        self._row(db_session, 501, 40)
        monkeypatch.setattr(notif_mod, "bot_instance", None)
        # Bot o'rnatilmagan — telegram manzili uchun 0 (hech narsa o'chirilmaydi)
        result = await backup_mod.prune_remote_backups()
        assert result.get("telegram", 0) == 0

    async def test_remote_keep_days_zero_disables(self, monkeypatch, backup_env, db_session):
        _tg_settings(monkeypatch, remote_keep_days=0)
        _patch_db_session(monkeypatch, db_session)
        import utils.notifications as notif_mod
        self._row(db_session, 601, 40)

        class _FakeBot:
            async def delete_message(self, chat_id, message_id):
                raise AssertionError("o'chirilgan bo'lsa yubormaslik kerak")

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        assert await backup_mod.prune_remote_backups() == {}


class TestRemoteKeepDaysConfig:
    def test_defaults_from_env(self, monkeypatch):
        import config as config_mod
        monkeypatch.setenv("BACKUP_REMOTE_KEEP_DAYS", "45")
        monkeypatch.setattr(config_mod, "BACKUP_UPLOAD_SETTINGS", {
            "remote": "s3",
            "remote_keep_days": int(
                config_mod.os.getenv("BACKUP_REMOTE_KEEP_DAYS", "") or 30),
        })
        assert backup_mod._remote_keep_days() == 45

    def test_zero_disables(self, monkeypatch):
        import config as config_mod
        monkeypatch.setattr(config_mod, "BACKUP_UPLOAD_SETTINGS", {
            "remote": "telegram",
            "remote_keep_days": 0,
        })
        assert backup_mod._remote_keep_days() == 0

    async def test_run_database_backup_includes_remote_pruned_key(
            self, monkeypatch, backup_env):
        # Uzoq joy yoqilmagan — bo'sh dict qaytadi, xato chiqarmaydi
        result = await backup_mod.run_database_backup(notify=False)
        assert result["remote_pruned"] == {}


class TestUploadErrorCapture:
    async def test_telegram_error_captured_in_box(self, monkeypatch, backup_env):
        """Xatolik `_errors` qutisiga yoziladi — SystemLog uchun sabab"""
        _set_upload(monkeypatch, remote="telegram")
        import utils.notifications as notif_mod
        monkeypatch.setattr(notif_mod, "bot_instance", None)  # bot yo'q

        errors = {}
        ok = await backup_mod.upload_backup_to_telegram(
            str(backup_env["src_db"]), _errors=errors)
        assert ok is False
        assert "Bot instance" in errors.get("message", "")

    async def test_telegram_success_no_error(self, monkeypatch, backup_env):
        _set_upload(monkeypatch, remote="telegram")
        import utils.notifications as notif_mod

        class _FakeBot:
            async def send_document(self, chat_id, document, caption=None):
                return type("Msg", (), {"message_id": 7})()

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())
        errors = {}
        ok = await backup_mod.upload_backup_to_telegram(
            str(backup_env["src_db"]), _errors=errors)
        assert ok is True
        assert errors == {}

    def test_s3_http_error_captured(self, monkeypatch, backup_env):
        _set_upload(monkeypatch, remote="s3")

        def fake_open(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 403, "Forbidden", {},
                io.BytesIO(b"<Error><Code>AccessDenied</Code></Error>"))

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fake_open)
        errors = {}
        assert backup_mod.upload_backup_to_s3(
            backup_env["src_db"], _errors=errors) is False
        assert "HTTP 403" in errors.get("message", "")

    async def test_remote_result_includes_errors(self, monkeypatch, backup_env):
        """upload_backup_to_remote: har bir manzil uchun xatolik sababi ham keladi"""
        _set_upload(monkeypatch, remote="s3")

        class _FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_open(req, timeout=None):
            return _FakeResp()

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fake_open)
        res = await backup_mod.upload_backup_to_remote(backup_env["src_db"])
        assert res["targets"]["s3"] is True
        assert res["errors"]["s3"] is None

        # Endi S3 xatolik bersa — sabab errors da
        def fail_open(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 500, "Server Error", {},
                io.BytesIO(b"oops"))

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fail_open)
        res2 = await backup_mod.upload_backup_to_remote(backup_env["src_db"])
        assert res2["targets"]["s3"] is False
        assert "HTTP 500" in (res2["errors"]["s3"] or "")


class TestBackupRunLogDetails:
    def test_details_json_structure(self):
        raw = backup_mod.backup_run_details_json(
            filename="backup_x.db", created=True, pruned=2,
            remote_pruned={"telegram": 1}, encrypted=True,
            uploaded={"telegram": True, "s3": False},
            upload_errors={"telegram": None, "s3": "HTTP 403"},
            targets_configured=True, source="web")
        data = backup_mod.parse_backup_run_details(raw)
        assert data is not None
        assert data["kind"] == "backup_run"
        assert data["filename"] == "backup_x.db"
        assert data["source"] == "web"
        assert data["encrypted"] is True
        assert data["targets_configured"] is True
        assert data["uploads"]["telegram"] == {"status": "ok", "error": None}
        assert data["uploads"]["s3"] == {"status": "failed", "error": "HTTP 403"}

    def test_parse_ignores_foreign_details(self):
        assert backup_mod.parse_backup_run_details(None) is None
        assert backup_mod.parse_backup_run_details("oddiy matn") is None
        assert backup_mod.parse_backup_run_details('{"boshqa": 1}') is None
        assert backup_mod.parse_backup_run_details('[1,2]') is None

    def test_build_log_action(self):
        action = backup_mod.build_backup_log_action(
            created="/backups/backup_x.db", pruned=1,
            uploaded={"telegram": True}, targets_configured=True,
            remote_pruned={"s3": 3}, encrypted=True)
        assert "backup_x.db" in action
        assert "yuklandi" in action
        assert "3 eski o'chirildi" in action

    async def test_notify_writes_structured_details(self, monkeypatch, db_session):
        """_notify_backup SystemLog'ga details JSON bilan yozadi"""
        import database.crud as crud_mod
        import database.session as session_mod
        _patch_db_session(monkeypatch, db_session)

        logged = []
        monkeypatch.setattr(crud_mod, "create_system_log",
                            lambda db, **kw: logged.append(kw))
        import utils.notifications as notif_mod

        async def fake_send(title, message, ntype):
            return True
        monkeypatch.setattr(notif_mod, "send_notification_to_admins", fake_send)

        await backup_mod._notify_backup(
            {"created": "/backups/backup_x.db", "pruned": 0,
             "remote_pruned": {}, "error": None})

        assert len(logged) == 1
        details = backup_mod.parse_backup_run_details(logged[0]["details"])
        assert details is not None
        assert details["filename"] == "backup_x.db"
        assert details["source"] == "scheduled"
        assert details["created"] is True

    async def test_notify_failed_backup_marks_error(self, monkeypatch, db_session):
        import database.crud as crud_mod
        import database.session as session_mod
        _patch_db_session(monkeypatch, db_session)

        logged = []
        monkeypatch.setattr(crud_mod, "create_system_log",
                            lambda db, **kw: logged.append(kw))
        import utils.notifications as notif_mod

        async def fake_send(title, message, ntype):
            return True
        monkeypatch.setattr(notif_mod, "send_notification_to_admins", fake_send)

        await backup_mod._notify_backup(
            {"created": None, "pruned": 0,
             "remote_pruned": {}, "error": "Disk to'ldi"})
        details = backup_mod.parse_backup_run_details(logged[0]["details"])
        assert details is not None
        assert details["created"] is False
        assert details["error"] == "Disk to'ldi"

    def test_list_backup_run_logs_parses_only_backup_runs(self, db_session):
        """Faqat backup_run JSON'li loglar keladi; boshqa module loglar kirmaydi"""
        from database import crud
        crud.create_system_log(db_session, user_id=0, user_name="Tizim",
                               action="Avtomatik backup: /x/backup_a.db (pruned=0)",
                               module="backup", details=None)
        crud.create_system_log(db_session, user_id=0, user_name="Tizim",
                               action="boshqa modul", module="sales",
                               details="{\"kind\":\"backup_run\"}")
        raw = backup_mod.backup_run_details_json(
            filename="backup_b.db", created=True, pruned=1,
            uploaded={"telegram": True}, upload_errors={"telegram": None},
            source="web")
        crud.create_system_log(db_session, user_id=0, user_name="Tizim",
                               action="Web backup", module="backup",
                               details=raw)

        rows = backup_mod.list_backup_run_logs(db_session)
        assert len(rows) == 1
        assert rows[0]["filename"] == "backup_b.db"
        assert rows[0]["source"] == "web"
        assert rows[0]["uploads"]["telegram"]["status"] == "ok"
