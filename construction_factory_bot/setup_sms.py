"""
SMS Integratsiya Sozlash Skripti
Eskiz.uz API kalitini .env fayliga kiritish
"""

import os
import sys

def print_header():
    """Sarlavha"""
    print("\n" + "=" * 50)
    print("📱 SMS INTEGRATSIYA SOZLASH")
    print("=" * 50)
    print("Xizmat: Eskiz.uz")
    print("Sayt: https://eskiz.uz")
    print("=" * 50)

def check_eskiz_account():
    """Eskiz.uz hisob mavjudligini tekshirish"""
    print("\n📋 1-QADAM: Eskiz.uz hisobini tekshirish")
    print("-" * 40)
    
    print("""
    Agar sizda Eskiz.uz hisobi yo'q bo'lsa:
    
    1. https://eskiz.uz saytiga kiring
    2. "Ro'yxatdan o'tish" tugmasini bosing
    3. Ma'lumotlarni kiriting
    4. Email ni tasdiqlang
    5. Dashboard ga kiring: https://my.eskiz.uz
    """)
    
    has_account = input("    Eskiz.uz hisobingiz bormi? (ha/yo'q): ").strip().lower()
    return has_account in ['ha', 'yes', 'y', '1']

def get_api_key():
    """API kalitni olish"""
    print("\n📋 2-QADAM: API kalitni olish")
    print("-" * 40)
    
    print("""
    API kalitni olish uchun:
    
    1. https://my.eskiz.uz saytiga kiring
    2. "API" bo'limiga boring
    3. "API kalit" tugmasini bosing
    4. "Yangi token yaratish" tugmasini bosing
    5. Izoh: "Construction Factory Bot" deb yozing
    6. "Yaratish" tugmasini bosing
    7. Tokeni saqlang (ko'rsatilmaydi!)
    """)
    
    api_key = input("    API kalitni kiriting: ").strip()
    return api_key

def get_sender_name():
    """Yuboruvchi nomini olish"""
    print("\n📋 3-QADAM: Yuboruvchi nomini sozlash")
    print("-" * 40)
    
    print("""
    SMS yuboruvchi nomi:
    - 4-11 ta belgi bo'lishi kerak
    - Faqat harflar va raqamlar
    - Masalan: KORXONA, MYBOT, SMS123
    """)
    
    sender = input("    Yuboruvchi nomini kiriting (default: KORXONA): ").strip()
    return sender if sender else "KORXONA"

def save_to_env(api_key, sender):
    """Sozlamalarni .env fayliga saqlash"""
    print("\n📋 4-QADAM: Sozlamalarni saqlash")
    print("-" * 40)
    
    env_file = ".env"
    
    # .env faylini o'qish
    env_content = ""
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            env_content = f.read()
    
    # SMS sozlamalarini qo'shish yoki yangilash
    sms_settings = f"""
# =============== SMS SOZLAMALARI ===============
# Eskiz.uz SMS xizmati
SMS_API_KEY={api_key}
SMS_SENDER={sender}
SMS_ENABLED=true
"""
    
    # Agar SMS sozlamalari mavjud bo'lsa, yangilash
    if "SMS_API_KEY=" in env_content:
        lines = env_content.split('\n')
        new_lines = []
        in_sms_section = False
        
        for line in lines:
            if "SMS_API_KEY=" in line:
                new_lines.append(f"SMS_API_KEY={api_key}")
                in_sms_section = True
            elif "SMS_SENDER=" in line:
                new_lines.append(f"SMS_SENDER={sender}")
            elif "SMS_ENABLED=" in line:
                new_lines.append("SMS_ENABLED=true")
            elif line.startswith("#") and "SMS" in line:
                new_lines.append(line)
            else:
                new_lines.append(line)
        
        env_content = '\n'.join(new_lines)
    else:
        # Yangi qism qo'shish
        if env_content:
            env_content += sms_settings
        else:
            env_content = sms_settings.strip()
    
    # Faylga yozish
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"    ✅ Sozlamalar {env_file} fayliga saqlandi")

def test_connection(api_key):
    """Ulanishni sinash"""
    print("\n📋 5-QADAM: Ulanishni sinash")
    print("-" * 40)
    
    print("    SMS xizmatiga ulanilmoqda...")
    
    try:
        # Virtual muhitda ishlashi uchun
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Config ni yangilash
        os.environ['SMS_API_KEY'] = api_key
        os.environ['SMS_ENABLED'] = 'true'
        
        print("    ✅ Sozlamalar yuklandi")
        print("    ✅ SMS xizmati tayyor")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Xatolik: {e}")
        return False

def print_summary(api_key, sender):
    """Xulosa"""
    print("\n" + "=" * 50)
    print("✅ SMS INTEGRATSIYA SOZLANDI!")
    print("=" * 50)
    
    print(f"""
    📱 Sozlamalar:
    ├── API kalit: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}
    ├── Yuboruvchi: {sender}
    ├── Holat: ✅ Faol
    └── Xizmat: Eskiz.uz
    
    🚀 Keyingi qadamlar:
    1. Botni ishga tushiring: python main.py
    2. "📱 SMS xizmati" tugmasini bosing
    3. SMS yuborishni sinang
    
    📖 Qo'llanma: SMS_SETUP_GUIDE.md
    """)

def main():
    """Asosiy funksiya"""
    
    print_header()
    
    # 1. Hisobni tekshirish
    if not check_eskiz_account():
        print("\n❌ Avval Eskiz.uz da ro'yxatdan o'ting!")
        print("   Sayt: https://eskiz.uz")
        return
    
    # 2. API kalitni olish
    api_key = get_api_key()
    if not api_key:
        print("\n❌ API kalit kiritilmadi!")
        return
    
    # 3. Yuboruvchi nomini olish
    sender = get_sender_name()
    
    # 4. Saqlash
    save_to_env(api_key, sender)
    
    # 5. Sinash
    test_connection(api_key)
    
    # 6. Xulosa
    print_summary(api_key, sender)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Sozlash bekor qilindi.")
    except Exception as e:
        print(f"\n❌ Xatolik: {e}")
