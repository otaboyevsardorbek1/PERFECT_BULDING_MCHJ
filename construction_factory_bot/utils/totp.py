"""
Google Authenticator (TOTP — RFC 6238) moduli.

TZ: "Direktor va kassir uchun Google Authenticator (2FA)" — parol + bir martalik
6 xonali kod bilan ikki bosqichli kirish.

- TOTP faqat standart kutubxona (hmac/hashlib/base64/struct) bilan hisoblanadi
  — yangi dependency kerak emas.
- QR kod (provisioning URI) uchun `qrcode` kutubxonasi ishlatiladi (u allaqachon
  requirements.txt da bor); u o'rnatilmagan bo'lsa QR o'rniga faqat secret qaytadi.
"""
import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
import urllib.parse

# =============== ASOSIY TOTP (RFC 6238, HMAC-SHA1, 6 raqam, 30 soniya) ===============

def normalize_secret(secret: str) -> str:
    """Base32 secretni tozalaydi: probel, chiziqcha va kichik harflarni moslaydi"""
    return "".join(ch for ch in (secret or "").upper() if ch not in " -=.,:;_")


def _base32_decode(secret: str) -> bytes:
    s = normalize_secret(secret)
    if not s:
        raise ValueError("Bo'sh TOTP secret")
    pad = "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s + pad)


def _hotp(secret_bytes: bytes, counter: int, digits: int = 6) -> str:
    """HMAC-SHA1 asosidagi bir martalik parol (RFC 4226)"""
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10 ** digits)).zfill(digits)


def totp_code(secret: str, at_time=None, digits: int = 6, period: int = 30) -> str:
    """Joriy (yoki at_time dagi) 6 xonali TOTP kodini qaytaradi"""
    t = int(time.time()) if at_time is None else int(at_time)
    return _hotp(_base32_decode(secret), t // period, digits)


def verify_totp(secret: str, code, at_time=None, window: int = 1) -> bool:
    """Kiritilgan kodni ±window*30 soniya oyna ichida tekshiradi (default ±30s)"""
    code = (code or "").strip()
    if not code:
        return False
    t = int(time.time()) if at_time is None else int(at_time)
    try:
        for i in range(-window, window + 1):
            if hmac.compare_digest(_hotp(_base32_decode(secret), (t + i * 30) // 30), code):
                return True
    except (ValueError, TypeError):
        return False
    return False


def generate_secret(bits: int = 160) -> str:
    """Yangi base32 secret yaratadi (Google Authenticator bilan mos, 32 belgi)"""
    return base64.b32encode(secrets.token_bytes(bits // 8)).decode("ascii").rstrip("=")


def provisioning_uri(secret: str, account_name: str, issuer: str = "Perfect Building") -> str:
    """Google Authenticator'ga qo'shish uchun otpauth:// URI"""
    label = urllib.parse.quote(f"{issuer}:{account_name}", safe=":")
    params = urllib.parse.urlencode({
        "secret": normalize_secret(secret),
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": 6,
        "period": 30,
    })
    return f"otpauth://totp/{label}?{params}"


def qr_png_bytes(secret: str, account_name: str, issuer: str = "Perfect Building") -> bytes:
    """Provisioning URI ni PNG baytlariga aylantiradi (bot rasm yuborishi uchun).

    `qrcode` kutubxonasi yo'q bo'lsa None qaytaradi.
    """
    try:
        import qrcode  # noqa: PLC0415
    except ImportError:
        return None
    qr = qrcode.QRCode(
        version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8, border=2,
    )
    qr.add_data(provisioning_uri(secret, account_name, issuer))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def qr_data_url(secret: str, account_name: str, issuer: str = "Perfect Building") -> str:
    """Provisioning URI ni PNG QR rasm sifatida base64 data URL qilib qaytaradi.

    `qrcode` kutubxonasi yo'q bo'lsa None qaytaradi (faqat secret yetarli).
    """
    try:
        import qrcode  # noqa: PLC0415 — requirements.txt da bor
    except ImportError:
        return None
    qr = qrcode.QRCode(
        version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8, border=2,
    )
    qr.add_data(provisioning_uri(secret, account_name, issuer))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")