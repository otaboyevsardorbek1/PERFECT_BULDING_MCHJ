"""
DATABASE BACKUP / RESTORE REST API testlari:
- GET  /api/backups           — tarix va hajmlar (faqat admin)
- POST /api/backups           — qo'lda backup olish
- POST /api/backups/restore   — backup'dan tiklash (xavfsizlik nusxasi bilan)

config.SQLITE_DB_PATH / BACKUP_DIR vaqtinchalik fayllarga yo'naltiriladi —
haqiqiy loyiha DB'siga tegmaydi.
"""
import io
import sqlite3
import urllib.error

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models
from database.session import get_db


@pytest.fixture
def db_file(tmp_path):
    """Diskdagi kichik haqiqiy SQLite fayl (backup manbai sifatida)"""
    path = tmp_path / "construction.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO products (name) VALUES ('Sement')")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def env(db_file, tmp_path, monkeypatch):
    """Backup manzillarini vaqtinchalik papkaga yo'naltiradi"""
    import config as config_mod
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(config_mod, "SQLITE_DB_PATH", str(db_file))
    monkeypatch.setattr(config_mod, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(config_mod, "USE_POSTGRESQL", False)
    return {"db_file": db_file, "backup_dir": backup_dir}


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = Session()
    yield s
    s.close()
    models.Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session, env):
    from dashboard.app import app

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _row_count(path):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    finally:
        conn.close()


class TestBackupAPI:
    def test_list_empty(self, client):
        r = client.get("/api/backups")
        assert r.status_code == 200
        body = r.json()
        assert body["backups"] == []
        assert body["count"] == 0
        # Sozlamalar ham keladi (web UI uchun)
        assert "settings" in body
        assert "keep_days" in body["settings"]

    def test_take_backup_then_list_with_size(self, client, env):
        r = client.post("/api/backups")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["filename"].startswith("backup_")
        assert body["filename"].endswith(".db")
        assert body["size_mb"] > 0
        # Uzoq joy sozlanmagan — bo'sh natijalar
        assert body["uploads"] == {}
        assert body["remote_pruned"] == {}

        lst = client.get("/api/backups")
        files = lst.json()["backups"]
        assert len(files) == 1
        assert files[0]["filename"] == body["filename"]
        assert files[0]["size_bytes"] > 0
        assert files[0]["size_mb"] > 0
        assert files[0]["created_at"]

    def test_upload_status_stored_in_system_log(self, client, env, monkeypatch):
        """Web backup SystemLog'ga yuklash holati (JSON) bilan yoziladi"""
        import config as config_mod
        monkeypatch.setattr(config_mod, "BACKUP_UPLOAD_SETTINGS", {
            "remote": "telegram,s3",
            "telegram_channel": "-100111222333",
            "s3_endpoint": "https://s3.example.test",
            "s3_region": "us-east-1",
            "s3_bucket": "backup-test",
            "s3_access_key": "AKIDEXAMPLE",
            "s3_secret_key": "s3cr3tsecretkey",
            "s3_prefix": "backups",
            "remote_keep_days": 30,
        })
        import utils.backup as backup_mod

        class _FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_open(req, timeout=None):
            return _FakeResp()

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fake_open)
        import utils.notifications as notif_mod

        class _FakeBot:
            async def send_document(self, chat_id, document, caption=None):
                return type("Msg", (), {"message_id": 42})()

            async def delete_message(self, chat_id, message_id):
                pass

        monkeypatch.setattr(notif_mod, "bot_instance", _FakeBot())

        r = client.post("/api/backups")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["uploads"].get("telegram") is True
        assert body["uploads"].get("s3") is True
        assert body["encrypted"] is False

        # SystemLog'da struktur details bor
        lst = client.get("/api/backups").json()
        logs = lst["upload_logs"]
        assert len(logs) >= 1
        top = logs[0]
        assert top["filename"] == body["filename"]
        assert top["source"] == "web"
        assert top["uploads"]["telegram"]["status"] == "ok"
        assert top["uploads"]["s3"]["status"] == "ok"

    def test_upload_failure_stored_in_system_log(self, client, env, monkeypatch):
        """Yuklash xatosiz bo'lsa — sabab ham logda"""
        import config as config_mod
        monkeypatch.setattr(config_mod, "BACKUP_UPLOAD_SETTINGS", {
            "remote": "s3",
            "telegram_channel": "",
            "s3_endpoint": "https://s3.example.test",
            "s3_region": "us-east-1",
            "s3_bucket": "backup-test",
            "s3_access_key": "AKIDEXAMPLE",
            "s3_secret_key": "s3cr3tsecretkey",
            "s3_prefix": "backups",
            "remote_keep_days": 30,
        })
        import utils.backup as backup_mod

        def fail_open(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 403, "Forbidden", {},
                io.BytesIO(b"<Error>AccessDenied</Error>"))

        monkeypatch.setattr(backup_mod, "_s3_urlopen", fail_open)

        r = client.post("/api/backups")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["uploads"].get("s3") is False
        assert "HTTP 403" in (body["upload_errors"].get("s3") or "")

        logs = client.get("/api/backups").json()["upload_logs"]
        top = logs[0]
        assert top["filename"] == body["filename"]
        assert top["uploads"]["s3"]["status"] == "failed"
        assert "HTTP 403" in (top["uploads"]["s3"]["error"] or "")


    def test_restore_missing_filename_400(self, client):
        r = client.post("/api/backups/restore", json={})
        assert r.status_code == 400

    def test_restore_unknown_file_400(self, client):
        r = client.post("/api/backups/restore",
                        json={"filename": "backup_19990101_000000.db"})
        assert r.status_code == 400
        body = r.json()
        assert "topilmadi" in (body.get("detail") or body.get("error") or "")

    def test_restore_rolls_database_back(self, client, env):
        # 1) Backup: 1 qator holat
        taken = client.post("/api/backups").json()
        # 2) DB ga yangi yozuv qo'shiladi
        conn = sqlite3.connect(str(env["db_file"]))
        conn.execute("INSERT INTO products (name) VALUES ('Noto''g''ri' )")
        conn.commit()
        conn.close()
        assert _row_count(env["db_file"]) == 2

        # 3) Backup'dan tiklash -> 1 qator qaytadi + xavfsizlik nusxasi olinadi
        r = client.post("/api/backups/restore",
                        json={"filename": taken["filename"]})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["filename"] == taken["filename"]
        assert body["safety_backup"] is not None
        assert body["safety_backup"] != taken["filename"]
        assert _row_count(env["db_file"]) == 1

        # 4) Tarixda manba + xavfsizlik nusxasi bor
        lst = client.get("/api/backups")
        files = [f["filename"] for f in lst.json()["backups"]]
        assert taken["filename"] in files
        assert body["safety_backup"] in files

    def test_restore_rejects_non_backup_name(self, client, env):
        bad = env["backup_dir"] / "notes.txt"
        bad.write_text("sqlite emas")
        r = client.post("/api/backups/restore", json={"filename": "notes.txt"})
        assert r.status_code == 400
