"""
Pytest konfiguratsiyasi va fixtures
"""

import os
import sys
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    """Database sessiya fixture - har bir test uchun alohida in-memory DB"""
    from database import models

    # Har bir test uchun yangi in-memory SQLite database yaratish
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    models.Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSession()

    yield session

    # Tozalash - sessionni yopish va engine ni dispose qilish
    session.close()
    models.Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(scope="function")
def test_db():
    """Test database fixture - in-memory DB bilan modellarni qaytaradi"""
    from database import models

    test_engine = create_engine("sqlite:///:memory:", echo=False)
    models.Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    yield models

    models.Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


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
