"""
Dashboard API endpoint testlari
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import models
from database.session import get_db_session


@pytest.fixture()
def authed_dashboard_client():
    """Root dashboard sahifasi endi login talab qiladi — direktor sifatida kiradi"""
    from dashboard.app import app
    from dashboard.auth import get_current_user, set_employee_password
    from database.session import get_db

    # In-memory DB (auth uchun) — real get_db override qilinadi
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    emp = models.Employee(
        full_name="Dashboard Admin", phone_number="+998900000050",
        position="Direktor", department="management",
        hire_date=datetime.utcnow(), is_admin=True, role="direktor",
    )
    session.add(emp)
    session.commit()
    session.refresh(emp)
    set_employee_password(session, emp, "parol1234")

    def _override_get_db():
        yield session

    app.dependency_overrides.pop(get_current_user, None)  # real login oqimi ishlaydi
    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    # Login (form) — cookie avtomatik saqlanadi. TestClient redirect'ni kuzatadi,
    # shuning uchun 303 (redirect) yoki 200 (follow natijasi) bo'lishi mumkin.
    r = client.post("/login", data={"phone": "+998900000050", "password": "parol1234"})
    assert r.status_code in (200, 303)
    assert client.cookies.get("web_token"), "login cookie o'rnatilmadi"
    yield client
    app.dependency_overrides.pop(get_db, None)
    session.close()
    models.Base.metadata.drop_all(engine)
    engine.dispose()


class TestDashboardAPI:
    """Dashboard API testlari"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Test sozlash"""
        from dashboard.app import app
        self.client = TestClient(app)
    
    def test_dashboard_home(self, authed_dashboard_client):
        """Dashboard bosh sahifasi (login talab qilinadi)"""
        response = authed_dashboard_client.get("/")
        
        assert response.status_code == 200
        assert "Qurilish Korxonasi Dashboard" in response.text
        assert "Mahsulotlar" in response.text  # real dashboard kontenti, login sahifasi emas
    
    def test_api_stats(self):
        """API statistika"""
        response = self.client.get("/api/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert "materials" in data
        assert "employees" in data
        assert "orders" in data
    
    def test_api_warehouse(self):
        """API ombor"""
        response = self.client.get("/api/warehouse")
        
        assert response.status_code == 200
        data = response.json()
        assert "materials" in data
        assert isinstance(data["materials"], list)
    
    def test_api_products(self):
        """API mahsulotlar"""
        response = self.client.get("/api/products")
        
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert isinstance(data["products"], list)
    
    def test_api_orders(self):
        """API buyurtmalar"""
        response = self.client.get("/api/orders")
        
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert isinstance(data["orders"], list)
    
    def test_api_stats_with_data(self, db_session):
        """Ma'lumotlar bilan API statistika"""
        # Test ma'lumotlar qo'shish
        material_data = {
            "name": "API Test Material",
            "unit": "kg",
            "current_stock": 1000,
            "min_stock": 100,
            "price_per_unit": 500
        }
        from database import crud
        crud.create_raw_material(db_session, material_data)
        
        response = self.client.get("/api/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["materials"] > 0


class TestDashboardHTML:
    """Dashboard HTML testlari (login orqali)"""
    
    def test_dashboard_contains_title(self, authed_dashboard_client):
        """Dashboard sarlavhasi"""
        response = authed_dashboard_client.get("/")
        
        assert response.status_code == 200
        assert "🏗️" in response.text
        assert "Dashboard" in response.text
    
    def test_dashboard_contains_stats(self, authed_dashboard_client):
        """Dashboard statistikasi"""
        response = authed_dashboard_client.get("/")
        
        assert "Mahsulotlar" in response.text
        assert "Xom ashyolar" in response.text
        assert "Xodimlar" in response.text
    
    def test_dashboard_contains_table(self, authed_dashboard_client):
        """Dashboard jadvali"""
        response = authed_dashboard_client.get("/")
        
        assert "<table>" in response.text
        assert "<th>" in response.text
