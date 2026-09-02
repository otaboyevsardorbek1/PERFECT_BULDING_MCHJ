"""
Dashboard API endpoint testlari
"""

import pytest
from fastapi.testclient import TestClient
from database import models
from database.session import get_db_session


class TestDashboardAPI:
    """Dashboard API testlari"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Test sozlash"""
        from dashboard.app import app
        self.client = TestClient(app)
    
    def test_dashboard_home(self):
        """Dashboard bosh sahifasi"""
        response = self.client.get("/")
        
        assert response.status_code == 200
        assert "Qurilish Korxonasi" in response.text
    
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
    """Dashboard HTML testlari"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Test sozlash"""
        from dashboard.app import app
        self.client = TestClient(app)
    
    def test_dashboard_contains_title(self):
        """Dashboard sarlavhasi"""
        response = self.client.get("/")
        
        assert "🏗️" in response.text
        assert "Dashboard" in response.text
    
    def test_dashboard_contains_stats(self):
        """Dashboard statistikasi"""
        response = self.client.get("/")
        
        assert "Mahsulotlar" in response.text
        assert "Xom ashyolar" in response.text
        assert "Xodimlar" in response.text
    
    def test_dashboard_contains_table(self):
        """Dashboard jadvali"""
        response = self.client.get("/")
        
        assert "<table>" in response.text
        assert "<th>" in response.text
