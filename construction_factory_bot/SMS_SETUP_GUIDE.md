# 📱 SMS Integratsiya Sozlash Qo'llanmasi (Eskiz.uz)

## 📋 Mundarija

1. [Eskiz.uz da ro'yxatdan o'tish](#1-eskizuz-da-royxatdan-otish)
2. [API key olish](#2-api-key-olish)
3. [Botga sozlash](#3-botga-sozlash)
4. [SMS yuborish](#4-sms-yuborish)
5. [Xatoliklarni tuzatish](#5-xatoliklarni-tuzatish)

---

## 1. Eskiz.uz da ro'yxatdan o'tish

### 1.1 Saytga kirish
- https://eskiz.uz saytiga kiring
- "Ro'yxatdan o'tish" tugmasini bosing

### 1.2 Ma'lumotlarni kiriting
- **Ism:** Sizning ismingiz
- **Email:** Email manzilingiz
- **Parol:** Kuchli parol yarating
- **Telefon:** Telefon raqamingiz

### 1.3 Email ni tasdiqlash
- Email ga xabar keladi
- Tasdiqlash havolasini bosing

---

## 2. API key olish

### 2.1 Dashboard ga kirish
- https://my.eskiz.uz saytiga kiring
- Email va parol bilan kiring

### 2.2 API kalitni olish
1. **"API"** bo'limiga boring
2. **"API kalit"** yoki **"Token"** tugmasini bosing
3. **"Yangi token yaratish"** tugmasini bosing
4. **Izoh:** "Construction Factory Bot" deb yozing
5. **"Yaratish"** tugmasini bosing

### 2.3 Token ni saqlash
- Token ko'rsatiladi (masalan: `abc123def456...`)
- **Uni darhol saqlang!** Ko'rsatilmaydi

---

## 3. Botga sozlash

### 3.1 .env faylini tahrirlash

```bash
cd construction_factory_bot
nano .env
```

### 3.2 SMS sozlamalarini qo'shish

```env
# =============== SMS SOZLAMALARI ===============
# Eskiz.uz API kaliti
SMS_API_KEY=abc123def456ghi789jkl012

# SMS yuboruvchi nomi (4-11 ta belgi)
SMS_SENDER=KORXONA

# SMS xizmatini yoqish (true/false)
SMS_ENABLED=true
```

### 3.3 SMS sozlamalarini tekshirish

```bash
# Tekshirish
python -c "
from config import INTEGRATION_SETTINGS
print('SMS holati:', INTEGRATION_SETTINGS.get('sms_enabled'))
print('SMS provider:', INTEGRATION_SETTINGS.get('sms_provider'))
print('SMS sender:', INTEGRATION_SETTINGS.get('sms_sender'))
"
```

---

## 4. SMS yuborish

### 4.1 Bot orqali

1. Botni ishga tushiring: `python main.py`
2. **"📱 SMS xizmati"** tugmasini bosing
3. **"📱 SMS yuborish"** tugmasini bosing
4. Telefon raqamini kiriting: `+998901234567`
5. SMS matnini kiriting

### 4.2 Kod orqali

```python
import asyncio
from utils.sms_service import sms_service

async def test_sms():
    # Bitta SMS
    result = await sms_service.send_sms(
        phone_number="+998901234567",
        message="Test xabar"
    )
    print("Natija:", result)

# Ishga tushirish
asyncio.run(test_sms())
```

### 4.3 Ommaviy SMS

```python
async def test_bulk_sms():
    phones = [
        "+998901234567",
        "+998901234568",
        "+998901234569"
    ]
    
    result = await sms_service.send_bulk_sms(
        phone_numbers=phones,
        message="Ommaviy xabar"
    )
    print("Natija:", result)

asyncio.run(test_bulk_sms())
```

---

## 5. Xatoliklarni tuzatish

### 5.1 "SMS xizmati o'chirgan"

**Sabab:** `SMS_ENABLED=false`

**Yechim:**
```env
# .env faylida
SMS_ENABLED=true
```

### 5.2 "API key noto'g'ri"

**Sabab:** Noto'g'ri token kiritilgan

**Yechim:**
1. Eskiz.uz dashboardidan yangi token oling
2. .env faylida yangilang

### 5.3 "SMS yuborilmadi"

**Sabablar:**
- Balans yetarli emas
- Telefon raqam noto'g'ri
- Serverda muammo

**Yechim:**
1. Eskiz.uz da balansni tekshiring
2. Telefon raqam formatini tekshiring: `+998901234567`
3. Loglarni tekshiring: `logs/bot_*.log`

### 5.4 "Token olinmadi"

**Sabab:** API key noto'g'ri yoki serverda muammo

**Yechim:**
```python
# Debug rejimda
import logging
logging.basicConfig(level=logging.DEBUG)

# SMS service ni sinash
from utils.sms_service import sms_service
token = await sms_service._get_token()
print("Token:", token)
```

---

## 📊 SMS Narxlari (Eskiz.uz)

| Xizmat | Narx |
|--------|------|
| O'zbekiston bo'ylab | ~50 so'm/SMS |
| 1000 SMS | ~50,000 so'm |
| 10,000 SMS | ~400,000 so'm |

> **Eslatma:** Narxlar o'zgarishi mumkin. Eskiz.uz saytidan tekshiring.

---

## 🔒 Xavfsizlik

1. **API keyni saqlang** - .env faylda, git ga qo'shmang
2. **.gitignore ga qo'shing:**
   ```
   .env
   *.log
   ```
3. **Faqat kerakli odamlarga bering** - API keyni cheklang

---

## 📞 Qo'llab-quvvatlash

- **Eskiz.uz:** https://eskiz.uz
- **Telefon:** +998 71 200 00 00
- **Email:** info@eskiz.uz
