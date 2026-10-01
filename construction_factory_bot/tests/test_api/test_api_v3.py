"""
REST API v3 endpoint testlari (Node.js frontend uchun)
Read-only tekshiruvlar — real DB'ga yozilmaydi (yozuvlar CRUD testlarida).
"""
import pytest
from fastapi.testclient import TestClient


class TestAPIv3:
    """API v3 endpointlari"""

    @pytest.fixture(autouse=True)
    def setup(self):
        from dashboard.app import app
        self.client = TestClient(app)

    def test_api_customers_list(self):
        r = self.client.get("/api/customers")
        assert r.status_code == 200
        data = r.json()
        assert "customers" in data
        assert isinstance(data["customers"], list)

    def test_api_customers_search(self):
        r = self.client.get("/api/customers?q=test")
        assert r.status_code == 200
        assert isinstance(r.json()["customers"], list)

    def test_api_customer_not_found(self):
        r = self.client.get("/api/customers/999999")
        assert r.status_code == 404

    def test_api_suppliers(self):
        r = self.client.get("/api/suppliers")
        assert r.status_code == 200
        assert "suppliers" in r.json()

    def test_api_reorder_suggestions(self):
        r = self.client.get("/api/suppliers/reorder-suggestions")
        assert r.status_code == 200
        assert "suggestions" in r.json()

    def test_api_receipts(self):
        r = self.client.get("/api/receipts")
        assert r.status_code == 200
        assert "receipts" in r.json()

    def test_api_reservations(self):
        r = self.client.get("/api/reservations")
        assert r.status_code == 200
        assert "reservations" in r.json()

    def test_api_transfers(self):
        r = self.client.get("/api/transfers")
        assert r.status_code == 200
        assert "transfers" in r.json()

    def test_api_inventory_checks(self):
        r = self.client.get("/api/inventory-checks")
        assert r.status_code == 200
        assert "checks" in r.json()

    def test_api_finance_pl(self):
        r = self.client.get("/api/finance/pl")
        assert r.status_code == 200
        assert "report" in r.json()
        assert "net_profit" in r.json()["report"]

    def test_api_finance_tax_calc(self):
        # Sof funksiya: amount berilsa DB'ga tegilmaydi
        r = self.client.get("/api/finance/tax?amount=1200000&rate=12")
        assert r.status_code == 200
        assert r.json()["tax"]["qqs"] == 144000

    def test_api_finance_debts(self):
        r = self.client.get("/api/finance/debts")
        assert r.status_code == 200
        assert "total_debt" in r.json()
        assert "credit_sales" in r.json()

    def test_api_roles(self):
        r = self.client.get("/api/roles")
        assert r.status_code == 200
        assert "roles" in r.json()

    def test_api_product_units_unknown_product(self):
        r = self.client.get("/api/products/999999/units")
        assert r.status_code == 200
        assert "units" in r.json()

    def test_api_convert_missing_product(self):
        r = self.client.get("/api/convert", params={
            "product_id": 999999, "from_unit": "kg", "to_unit": "dona", "quantity": 5
        })
        assert r.status_code == 404

    def test_api_customer_segmentation(self):
        """Mijoz triaji — Oltin/Kumush/Bronza segmentatsiya (TZ)"""
        r = self.client.get("/api/customers/segmentation")
        assert r.status_code == 200
        data = r.json()
        assert "segmentation" in data
        assert set(["gold", "silver", "bronze", "total"]) <= set(data["segmentation"].keys())
        assert "tiers" in data

    def test_api_related_products_missing(self):
        """O'xshash mahsulot taklifi — topilmasa bo'sh ro'yxat (TZ cross-sell)"""
        r = self.client.get("/api/products/999999/related")
        assert r.status_code == 200
        assert "related" in r.json()
        assert isinstance(r.json()["related"], list)
