"""
Yordamchi funksiyalar to'plami
Construction Factory Bot uchun
"""

import os
import re
import json
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from decimal import Decimal
from pathlib import Path

# QR kod va JWT uchun
try:
    import qrcode
    from PIL import Image
    import jwt
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    print("QR code yoki JWT kutubxonalari o'rnatilmagan")


class HelperUtils:
    """Yordamchi funksiyalar sinfi"""
    
    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        """
        Telefon raqamini tekshirish
        
        Args:
            phone: Telefon raqami
            
        Returns:
            bool: To'g'ri formatda bo'lsa True
        """
        if not phone:
            return False
            
        patterns = [
            r'^\+998\d{9}$',      # +998901234567
            r'^998\d{9}$',        # 998901234567
            r'^\d{9}$',           # 901234567
            r'^\+998\s\d{2}\s\d{3}\s\d{2}\s\d{2}$',  # +998 90 123 45 67
            r'^\(\d{3}\)\s?\d{3}-\d{4}$',            # (998) 901-2345 (variant)
        ]
        
        for pattern in patterns:
            if re.match(pattern, phone.strip()):
                return True
        
        return False
    
    @staticmethod
    def normalize_phone_number(phone: str) -> str:
        """
        Telefon raqamini standart formatga keltirish
        
        Args:
            phone: Telefon raqami
            
        Returns:
            str: Standart formatdagi telefon raqami
        """
        if not phone:
            return ""
        
        # Faqat raqamlarni olish
        numbers = re.sub(r'\D', '', phone)
        
        if len(numbers) == 9:
            # 901234567 -> +998901234567
            return f"+998{numbers}"
        elif len(numbers) == 12 and numbers.startswith('998'):
            # 998901234567 -> +998901234567
            return f"+{numbers}"
        elif len(numbers) == 13 and numbers.startswith('998'):
            # 998901234567 -> +998901234567
            return f"+{numbers}"
        else:
            # Boshqa formatda
            return f"+{numbers}" if numbers else ""
    
    @staticmethod
    def format_currency(amount: Union[float, int, Decimal, str]) -> str:
        """
        Pul miqdorini formatlash
        
        Args:
            amount: Miqdor
            
        Returns:
            str: Formatlangan summa
        """
        try:
            if amount is None:
                return "0 so'm"
            
            # Har qanday turdan float ga o'tkazish
            if isinstance(amount, str):
                amount = float(amount.replace(',', '.'))
            elif isinstance(amount, Decimal):
                amount = float(amount)
            elif isinstance(amount, int):
                amount = float(amount)
            
            # Formatlash
            if amount >= 1000000:
                # Millionlar uchun
                formatted = f"{amount/1000000:,.1f}".replace(',', ' ')
                return f"{formatted} mln so'm"
            elif amount >= 1000:
                # Minglar uchun
                formatted = f"{amount:,.0f}".replace(',', ' ')
                return f"{formatted} so'm"
            else:
                return f"{amount:,.0f} so'm".replace(',', ' ')
        except (ValueError, TypeError):
            return "0 so'm"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Foizni formatlash
        
        Args:
            value: Foiz qiymati
            decimals: Kasrlar soni
            
        Returns:
            str: Formatlangan foiz
        """
        try:
            if value is None:
                return "0%"
            return f"{value:.{decimals}f}%"
        except (ValueError, TypeError):
            return "0%"
    
    @staticmethod
    def format_datetime(dt: datetime, format_type: str = 'default') -> str:
        """
        Vaqtni formatlash
        
        Args:
            dt: datetime obyekti
            format_type: Format turi
            
        Returns:
            str: Formatlangan vaqt
        """
        if not dt:
            return ""
        
        formats = {
            'default': '%d.%m.%Y %H:%M',
            'date': '%d.%m.%Y',
            'time': '%H:%M',
            'full': '%d.%m.%Y %H:%M:%S',
            'iso': '%Y-%m-%d %H:%M:%S',
            'file': '%Y%m%d_%H%M%S',
            'human': '%d %B %Y, %H:%M'
        }
        
        fmt = formats.get(format_type, formats['default'])
        return dt.strftime(fmt)
    
    @staticmethod
    def generate_random_string(length: int = 8, 
                              include_digits: bool = True,
                              include_letters: bool = True) -> str:
        """
        Tasodifiy string yaratish
        
        Args:
            length: Uzunlik
            include_digits: Raqamlar qo'shilsinmi
            include_letters: Harflar qo'shilsinmi
            
        Returns:
            str: Tasodifiy string
        """
        chars = ''
        if include_letters:
            chars += string.ascii_letters
        if include_digits:
            chars += string.digits
        
        if not chars:
            chars = string.ascii_letters + string.digits
        
        return ''.join(random.choice(chars) for _ in range(length))
    
    @staticmethod
    def generate_unique_id(prefix: str = '') -> str:
        """
        Unikal ID yaratish
        
        Args:
            prefix: Old qo'shimcha
            
        Returns:
            str: Unikal ID
        """
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = ''.join(random.choice(string.digits) for _ in range(4))
        return f"{prefix}{timestamp}{random_part}"
    
    @staticmethod
    def generate_qr_code(data: str, 
                        filename: Optional[str] = None,
                        save_path: str = 'temp') -> Optional[str]:
        """
        QR kod yaratish
        
        Args:
            data: QR kodga yoziladigan ma'lumot
            filename: Fayl nomi (agar berilmasa, avtomatik)
            save_path: Saqlash papkasi
            
        Returns:
            Optional[str]: QR kod fayl yo'li yoki None
        """
        if not QR_AVAILABLE:
            print("QR code kutubxonasi o'rnatilmagan")
            return None
        
        try:
            # Papka yaratish
            Path(save_path).mkdir(parents=True, exist_ok=True)
            
            # Fayl nomi
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"qr_{timestamp}.png"
            
            filepath = os.path.join(save_path, filename)
            
            # QR kod yaratish
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Rasm yaratish
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(filepath)
            
            return filepath
            
        except Exception as e:
            print(f"QR kod yaratishda xatolik: {e}")
            return None
    
    @staticmethod
    def generate_jwt_token(data: Dict, 
                          secret_key: str, 
                          expires_in: int = 3600,
                          algorithm: str = "HS256") -> str:
        """
        JWT token yaratish
        
        Args:
            data: Token ichidagi ma'lumotlar
            secret_key: Maxfiy kalit
            expires_in: Token amal qilish muddati (sekund)
            algorithm: Shifrlash algoritmi
            
        Returns:
            str: JWT token
        """
        try:
            payload = data.copy()
            
            # Amal qilish muddati
            expire = datetime.utcnow() + timedelta(seconds=expires_in)
            payload.update({
                'exp': expire,
                'iat': datetime.utcnow()
            })
            
            # Token yaratish
            token = jwt.encode(payload, secret_key, algorithm=algorithm)
            
            # Python 3.10+ uchun
            if isinstance(token, bytes):
                token = token.decode('utf-8')
                
            return token
            
        except Exception as e:
            print(f"JWT token yaratishda xatolik: {e}")
            return ""
    
    @staticmethod
    def decode_jwt_token(token: str, 
                        secret_key: str,
                        algorithms: List[str] = ["HS256"]) -> Optional[Dict]:
        """
        JWT tokenni dekod qilish
        
        Args:
            token: JWT token
            secret_key: Maxfiy kalit
            algorithms: Ruxsat berilgan algoritmlar
            
        Returns:
            Optional[Dict]: Dekodlangan ma'lumotlar yoki None
        """
        try:
            payload = jwt.decode(token, secret_key, algorithms=algorithms)
            return payload
        except jwt.ExpiredSignatureError:
            print("Token muddati tugagan")
            return None
        except jwt.InvalidTokenError as e:
            print(f"Yaroqsiz token: {e}")
            return None
    
    @staticmethod
    def parse_date_string(date_str: str, 
                         formats: List[str] = None) -> Optional[datetime]:
        """
        Sana stringini datetime ga aylantirish
        
        Args:
            date_str: Sana stringi
            formats: Mumkin bo'lgan formatlar
            
        Returns:
            Optional[datetime]: datetime obyekti yoki None
        """
        if not date_str:
            return None
        
        if formats is None:
            formats = [
                '%d.%m.%Y',
                '%d/%m/%Y',
                '%Y-%m-%d',
                '%d.%m.%Y %H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%d %B %Y',
                '%d %b %Y'
            ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def calculate_age(birth_date: datetime) -> int:
        """
        Yoshni hisoblash
        
        Args:
            birth_date: Tug'ilgan sana
            
        Returns:
            int: Yosh
        """
        today = datetime.now()
        age = today.year - birth_date.year
        
        # Agar tug'ilgan kun hali o'tmagan bo'lsa
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    
    @staticmethod
    def human_readable_size(size_bytes: int) -> str:
        """
        Fayl hajmini inson o'qiydigan formatda ko'rsatish
        
        Args:
            size_bytes: Baytlardagi hajm
            
        Returns:
            str: Formatlangan hajm
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = 0
        
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100, 
                     suffix: str = "...") -> str:
        """
        Matnni kesish
        
        Args:
            text: Matn
            max_length: Maksimal uzunlik
            suffix: Oxiriga qo'shiladigan belgi
            
        Returns:
            str: Kesilgan matn
        """
        if len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """
        Xavfsiz integer ga o'tkazish
        
        Args:
            value: Qiymat
            default: Default qiymat
            
        Returns:
            int: Integer qiymat
        """
        try:
            if value is None:
                return default
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        """
        Xavfsiz float ga o'tkazish
        
        Args:
            value: Qiymat
            default: Default qiymat
            
        Returns:
            float: Float qiymat
        """
        try:
            if value is None:
                return default
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """
        Fayl kengaytmasini olish
        
        Args:
            filename: Fayl nomi
            
        Returns:
            str: Fayl kengaytmasi
        """
        return os.path.splitext(filename)[1].lower()
    
    @staticmethod
    def is_image_file(filename: str) -> bool:
        """
        Fayl rasm ekanligini tekshirish
        
        Args:
            filename: Fayl nomi
            
        Returns:
            bool: Rasm bo'lsa True
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        ext = HelperUtils.get_file_extension(filename)
        return ext in image_extensions
    
    @staticmethod
    def is_document_file(filename: str) -> bool:
        """
        Fayl hujjat ekanligini tekshirish
        
        Args:
            filename: Fayl nomi
            
        Returns:
            bool: Hujjat bo'lsa True
        """
        doc_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'}
        ext = HelperUtils.get_file_extension(filename)
        return ext in doc_extensions
    
    @staticmethod
    def create_directory(path: str) -> bool:
        """
        Papka yaratish
        
        Args:
            path: Papka yo'li
            
        Returns:
            bool: Muvaffaqiyatli bo'lsa True
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Papka yaratishda xatolik: {e}")
            return False
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """
        Fayl nomini tozalash (maxsus belgilarni olib tashlash)
        
        Args:
            filename: Fayl nomi
            
        Returns:
            str: Tozalangan fayl nomi
        """
        # Noto'g'ri belgilarni olib tashlash
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Ortiqcha bo'sh joylarni olib tashlash
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    @staticmethod
    def get_week_range(date: datetime = None) -> Tuple[datetime, datetime]:
        """
        Hafta boshi va oxirini olish
        
        Args:
            date: Sana (agar berilmasa, bugun)
            
        Returns:
            Tuple[datetime, datetime]: (hafta boshi, hafta oxiri)
        """
        if date is None:
            date = datetime.now()
        
        # Hafta boshi (Dushanba)
        start = date - timedelta(days=date.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Hafta oxiri (Yakshanba)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return start, end
    
    @staticmethod
    def get_month_range(date: datetime = None) -> Tuple[datetime, datetime]:
        """
        Oy boshi va oxirini olish
        
        Args:
            date: Sana (agar berilmasa, bugun)
            
        Returns:
            Tuple[datetime, datetime]: (oy boshi, oy oxiri)
        """
        if date is None:
            date = datetime.now()
        
        # Oy boshi
        start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Keyingi oy boshi
        if date.month == 12:
            next_month = date.replace(year=date.year + 1, month=1, day=1)
        else:
            next_month = date.replace(month=date.month + 1, day=1)
        
        # Oy oxiri
        end = next_month - timedelta(seconds=1)
        
        return start, end
    
    @staticmethod
    def calculate_days_between(start_date: datetime, end_date: datetime) -> int:
        """
        Ikki sana orasidagi kunlar soni
        
        Args:
            start_date: Boshlanish sanasi
            end_date: Tugash sanasi
            
        Returns:
            int: Kunlar soni
        """
        if not start_date or not end_date:
            return 0
        
        # Faqat sana qismini hisoblash
        start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        delta = end - start
        return abs(delta.days)
    
    @staticmethod
    def mask_sensitive_info(text: str, 
                           mask_char: str = '*',
                           visible_chars: int = 4) -> str:
        """
        Maxfiy ma'lumotlarni yashirish
        
        Args:
            text: Matn
            mask_char: Yashirish belgisi
            visible_chars: Ko'rinadigan belgilar soni
            
        Returns:
            str: Yashirilgan matn
        """
        if not text or len(text) <= visible_chars:
            return text
        
        # Telefon raqami
        if HelperUtils.validate_phone_number(text):
            normalized = HelperUtils.normalize_phone_number(text)
            if len(normalized) > 7:
                return normalized[:4] + mask_char * (len(normalized) - 7) + normalized[-3:]
        
        # Email
        elif '@' in text:
            parts = text.split('@')
            if len(parts) == 2:
                username = parts[0]
                domain = parts[1]
                if len(username) > 2:
                    masked_user = username[0] + mask_char * (len(username) - 2) + username[-1]
                    return f"{masked_user}@{domain}"
        
        # Oddiy matn
        if len(text) > visible_chars * 2:
            return text[:visible_chars] + mask_char * (len(text) - visible_chars * 2) + text[-visible_chars:]
        else:
            return mask_char * len(text)
    
    @staticmethod
    def generate_password(length: int = 12) -> str:
        """
        Xavfsiz parol yaratish
        
        Args:
            length: Parol uzunligi
            
        Returns:
            str: Xavfsiz parol
        """
        if length < 8:
            length = 8
        
        # Belgilar to'plami
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        
        # Har bir turdan kamida bitta belgi
        password_chars = [
            random.choice(lowercase),
            random.choice(uppercase),
            random.choice(digits),
            random.choice(symbols)
        ]
        
        # Qolgan belgilar
        all_chars = lowercase + uppercase + digits + symbols
        password_chars.extend(random.choice(all_chars) for _ in range(length - 4))
        
        # Aralashtirish
        random.shuffle(password_chars)
        
        return ''.join(password_chars)


# Funksiyalar uchun qisqa nomlar
validate_phone = HelperUtils.validate_phone_number
normalize_phone = HelperUtils.normalize_phone_number
format_currency = HelperUtils.format_currency
format_percent = HelperUtils.format_percentage
format_date = HelperUtils.format_datetime
generate_qr = HelperUtils.generate_qr_code
generate_jwt = HelperUtils.generate_jwt_token
decode_jwt = HelperUtils.decode_jwt_token

# Export qilinadigan funksiyalar
__all__ = [
    'HelperUtils',
    'validate_phone',
    'normalize_phone',
    'format_currency',
    'format_percent',
    'format_date',
    'generate_qr',
    'generate_jwt',
    'decode_jwt',
]
# # Yordamchi funksiyalar
# def validate_phone_number(phone: str) -> bool:
#     """Telefon raqamini tekshirish"""
#     import re
    
#     patterns = [
#         r'^\+998\d{9}$',  # +998901234567
#         r'^998\d{9}$',    # 998901234567
#         r'^\d{9}$',       # 901234567
#     ]
    
#     for pattern in patterns:
#         if re.match(pattern, phone):
#             return True
    
#     return False

# def format_currency(amount: float) -> str:
#     """Pul miqdorini formatlash"""
#     return f"{amount:,.0f} so'm".replace(",", " ")

# def generate_qr_code(data: str, filename: str = "qrcode.png") -> str:
#     """QR kod yaratish"""
#     import qrcode
#     from PIL import Image
    
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=10,
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)
    
#     img = qr.make_image(fill_color="black", back_color="white")
#     img.save(filename)
    
#     return filename

# def generate_jwt_token(data: dict, secret: str, expires_in: int = 3600) -> str:
#     """JWT token yaratish"""
#     import jwt
#     from datetime import datetime, timedelta
    
#     payload = data.copy()
#     payload['exp'] = datetime.utcnow() + timedelta(seconds=expires_in)
    
#     return jwt.encode(payload, secret, algorithm="HS256")