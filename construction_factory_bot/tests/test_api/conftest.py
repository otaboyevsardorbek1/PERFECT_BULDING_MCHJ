"""
test_api umumiy konfiguratsiyasi

FastAPI auth qatlami qo'shilgandan so'ng barcha /api so'rovlari token talab qiladi.
Eski API testlari buzilmasligi uchun bu yerda barcha so'rovlar direktor (admin)
sifatida o'tadi. Haqiqiy auth oqimi test_auth.py da alohida tekshiriladi.
"""
import pytest

from dashboard.app import app


@pytest.fixture(autouse=True)
def api_admin_override():
    """Hamma /api testlar admin sifatida o'tadi (auth'ni chetlab o'tmaydi, rolni beradi)"""
    from dashboard.auth import get_current_user

    class _AdminUser:
        id = 1
        full_name = "Test Admin"
        phone = "+998000000000"
        telegram_id = 123456789
        is_admin = True
        role = "direktor"

        def to_dict(self):
            return {"id": self.id, "full_name": self.full_name, "role": self.role,
                    "permissions": {"can_view": [], "can_edit": [], "see_cost": True}}

    app.dependency_overrides[get_current_user] = lambda: _AdminUser()
    yield
    app.dependency_overrides.pop(get_current_user, None)
