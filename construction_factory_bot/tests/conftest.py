"""
Pytest konfiguratsiyasi va fixtures
"""

import os
import sys
import pytest
from datetime import datetime, timedelta

# Loyiha yo'llarini qo'shish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test muhitini sozlash
os.environ['TEST_MODE'] = 'true'
os.environ['BOT_TOKEN'] = 'test_token_1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ'
os.environ['ADMIN_IDS'] = '123456789'


@pytest.fixture(scope="session")
def event_loop():
    """Asyncio event loop fixture"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Database sessiya fixture"""
    from database.session import get_db_session
    from database import models
    
    # Test database yaratish
    session = get_db_session()
    
    yield session
    
    # Tozalash
    session.close()


@pytest.fixture(scope="function")
def test_db():
    """Test database fixture"""
    from database import models
    from database.session import get_db_session
    
    # Database jadvallarini yaratish
    models.Base.metadata.create_all(bind=models.engine)
    
    yield models
    
    # Tozalash
    models.Base.metadata.drop_all(bind=models.engine)


@pytest.fixture
def sample_raw_material():
    """Namuna xom ashyo"""
    return {
        "name": "Test Klinker",
        "category": "Asosiy",
        "unit": "kg",
        "current_stock": 10000,
        "min_stock": 1000,
        "price_per_unit": 500,
        "supplier": "Test Supplier"
    }


@pytest.fixture
def sample_product():
    """Namuna mahsulot"""
    return {
        "name": "Test Sement M500",
        "category": "sement",
        "unit": "qop",
        "selling_price": 12000,
        "production_cost": 7000,
        "profit_margin": 0.4,
        "description": "Test mahsulot",
        "is_active": True
    }


@pytest.fixture
def sample_employee():
    """Namuna xodim"""
    return {
        "full_name": "Test Ishchi",
        "phone_number": "+998901234567",
        "position": "Ishchi",
        "department": "Ishlab chiqarish",
        "status": "active",
        "hire_date": datetime.now(),
        "salary": 2500000
    }


@pytest.fixture
def sample_financial_data():
    """Namuna moliyaviy ma'lumotlar"""
    return {
        "total_sales_amount": 15000000,
        "production_costs": 8000000,
        "salary_costs": 3000000,
        "utility_costs": 500000,
        "other_expenses": 200000,
        "total_costs": 11700000,
        "net_profit": 3300000,
        "profit_margin": 22.0,
        "other_income": 0
    }


@pytest.fixture
def sample_order():
    """Namuna buyurtma"""
    return {
        "product_name": "Sement M500 (50kg)",
        "quantity": 100,
        "total_cost": 700000,
        "status": "jarayonda"
    }


@pytest.fixture
def mock_user():
    """Foydalanuvchi mock"""
    class MockUser:
        def __init__(self):
            self.id = 123456789
            self.username = "test_user"
            self.full_name = "Test Foydalanuvchi"
            self.is_bot = False
    
    return MockUser()


@pytest.fixture
def mock_message():
    """Xabar mock"""
    class MockMessage:
        def __init__(self):
            self.text = "/start"
            self.from_user = MockUser()
            self.chat = MockChat()
        
        async def answer(self, text, parse_mode=None, reply_markup=None):
            return {"text": text, "parse_mode": parse_mode}
        
        async def answer_document(self, document, caption=None):
            return {"document": document, "caption": caption}
    
    class MockUser:
        def __init__(self):
            self.id = 123456789
            self.username = "test_user"
            self.full_name = "Test Foydalanuvchi"
    
    class MockChat:
        def __init__(self):
            self.id = 123456789
    
    return MockMessage()
