"""
Tranzaksiya kodi — TZ (A-bo'lim: "Tranzaksiya kodi")

Har bir operatsiyaga (sotuv, kirim, chiqim, qaytarish) **unikal 16 xonali
raqamli kod** beriladi. Bu kod orqali soliqchilar tekshiruvida hujjat
1 daqiqada topiladi.

Format: YYMMDD + 10 tasodifiy raqam  ->  16 xonali kod.
To'qnashuv ehtimoli amalda nolga teng (10^10 tasodifiy maydon).
"""
import random
from datetime import datetime

_rng = random.SystemRandom()


def make_transaction_code() -> str:
    """YYMMDD (6) + 10 tasodifiy raqam = 16 xonali unikal tranzaksiya kodi."""
    prefix = datetime.now().strftime("%y%m%d")
    suffix = "".join(str(_rng.randrange(10)) for _ in range(10))
    return prefix + suffix


def is_valid_transaction_code(code: str) -> bool:
    """Kod 16 xonali raqam ekanini tekshiradi."""
    return bool(code) and len(code) == 16 and code.isdigit()