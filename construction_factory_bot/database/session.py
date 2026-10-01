from sqlalchemy.orm import Session
from .models import SessionLocal

def get_db():
    """Database sessiyasini olish"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Sessiya obyektini olish"""
    return SessionLocal()