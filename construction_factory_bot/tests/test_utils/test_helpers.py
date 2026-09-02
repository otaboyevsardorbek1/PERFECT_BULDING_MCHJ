"""
Helper funksiyalar uchun unit testlar
"""

import pytest
from utils.helpers import (
    HelperUtils,
    validate_phone,
    normalize_phone,
    format_currency,
    format_percent,
    format_date
)


class TestValidatePhone:
    """Telefon raqamini tekshirish testlari"""
    
    def test_valid_uzbek_phone(self):
        """To'g'ri O'zbekiston telefon raqami"""
        assert validate_phone("+998901234567") == True
    
    def test_valid_uzbek_phone_without_plus(self):
        """Plus belgisisiz O'zbekiston raqami"""
        assert validate_phone("998901234567") == True
    
    def test_valid_local_phone(self):
        """Mahalliy raqam"""
        assert validate_phone("901234567") == True
    
    def test_invalid_phone_too_short(self):
        """Qisqa raqam"""
        assert validate_phone("123") == False
    
    def test_invalid_phone_letters(self):
        """Harflar bilan"""
        assert validate_phone("abc1234567") == False
    
    def test_empty_phone(self):
        """Bo'sh raqam"""
        assert validate_phone("") == False
    
    def test_none_phone(self):
        """None qiymat"""
        assert validate_phone(None) == False


class TestNormalizePhone:
    """Telefon raqamini formatlash testlari"""
    
    def test_normalize_local(self):
        """Mahalliy raqamni formatlash"""
        result = normalize_phone("901234567")
        assert result == "+998901234567"
    
    def test_normalize_with_country_code(self):
        """Mamlakat kodi bilan"""
        result = normalize_phone("998901234567")
        assert result == "+998901234567"
    
    def test_normalize_with_plus(self):
        """Plus belgisi bilan"""
        result = normalize_phone("+998901234567")
        assert result == "+998901234567"
    
    def test_normalize_empty(self):
        """Bo'sh raqam"""
        result = normalize_phone("")
        assert result == ""


class TestFormatCurrency:
    """Pul miqdorini formatlash testlari"""
    
    def test_format_large_amount(self):
        """Katta summa"""
        result = format_currency(1500000)
        assert "mln" in result.lower() or "1,500,000" in result
    
    def test_format_medium_amount(self):
        """O'rtacha summa"""
        result = format_currency(50000)
        assert "50" in result and "so'm" in result
    
    def test_format_small_amount(self):
        """Kichik summa"""
        result = format_currency(1000)
        assert "1" in result and "so'm" in result
    
    def test_format_zero(self):
        """Nol"""
        result = format_currency(0)
        assert "0" in result
    
    def test_format_none(self):
        """None qiymat"""
        result = format_currency(None)
        assert "0" in result


class TestFormatPercent:
    """Foizni formatlash testlari"""
    
    def test_format_percent_normal(self):
        """Oddiy foiz"""
        result = format_percent(25.5)
        assert "25.5%" in result
    
    def test_format_percent_zero(self):
        """Nol foiz"""
        result = format_percent(0)
        assert "0%" in result
    
    def test_format_percent_hundred(self):
        """100%"""
        result = format_percent(100)
        assert "100" in result and "%" in result


class TestFormatDate:
    """Sanani formatlash testlari"""
    
    def test_format_date_default(self):
        """Default format"""
        from datetime import datetime
        dt = datetime(2024, 1, 15, 10, 30)
        result = format_date(dt)
        assert "15.01.2024" in result
    
    def test_format_date_empty(self):
        """Bo'sh sana"""
        result = format_date(None)
        assert result == ""


class TestGenerateRandomString:
    """Tasodifiy string yaratish testlari"""
    
    def test_generate_random_string(self):
        """Tasodifiy string"""
        result = HelperUtils.generate_random_string(10)
        assert len(result) == 10
    
    def test_generate_random_string_length(self):
        """Uzunlikni tekshirish"""
        result = HelperUtils.generate_random_string(20)
        assert len(result) == 20
    
    def test_generate_random_string_digits_only(self):
        """Faqat raqamlar"""
        result = HelperUtils.generate_random_string(10, include_letters=False)
        assert result.isdigit()
    
    def test_generate_random_string_letters_only(self):
        """Faqat harflar"""
        result = HelperUtils.generate_random_string(10, include_digits=False)
        assert result.isalpha()


class TestGenerateUniqueId:
    """Unikal ID yaratish testlari"""
    
    def test_generate_unique_id(self):
        """Unikal ID"""
        result = HelperUtils.generate_unique_id()
        assert len(result) > 0
    
    def test_generate_unique_id_with_prefix(self):
        """Prefiks bilan"""
        result = HelperUtils.generate_unique_id("INV-")
        assert result.startswith("INV-")


class TestSafeConversion:
    """Xavfsiz o'tkazish testlari"""
    
    def test_safe_int_valid(self):
        """To'g'ri integer"""
        assert HelperUtils.safe_int("123") == 123
    
    def test_safe_int_invalid(self):
        """Noto'g'ri qiymat"""
        assert HelperUtils.safe_int("abc") == 0
    
    def test_safe_int_none(self):
        """None qiymat"""
        assert HelperUtils.safe_int(None) == 0
    
    def test_safe_float_valid(self):
        """To'g'ri float"""
        assert HelperUtils.safe_float("123.45") == 123.45
    
    def test_safe_float_invalid(self):
        """Noto'g'ri qiymat"""
        assert HelperUtils.safe_float("abc") == 0.0
    
    def test_safe_float_none(self):
        """None qiymat"""
        assert HelperUtils.safe_float(None) == 0.0


class TestFileUtils:
    """Fayl utilitikalari testlari"""
    
    def test_get_file_extension(self):
        """Fayl kengaytmasini olish"""
        assert HelperUtils.get_file_extension("test.pdf") == ".pdf"
        assert HelperUtils.get_file_extension("test.xlsx") == ".xlsx"
    
    def test_is_image_file(self):
        """Rasm faylini aniqlash"""
        assert HelperUtils.is_image_file("test.jpg") == True
        assert HelperUtils.is_image_file("test.png") == True
        assert HelperUtils.is_image_file("test.pdf") == False
    
    def test_is_document_file(self):
        """Hujjat faylini aniqlash"""
        assert HelperUtils.is_document_file("test.pdf") == True
        assert HelperUtils.is_document_file("test.xlsx") == True
        assert HelperUtils.is_document_file("test.jpg") == False
    
    def test_clean_filename(self):
        """Fayl nomini tozalash"""
        result = HelperUtils.clean_filename("test<>:file.txt")
        assert "<" not in result
        assert ">" not in result
    
    def test_truncate_text(self):
        """Matnni kesish"""
        result = HelperUtils.truncate_text("Uzun matn", 5)
        assert len(result) <= 8  # 5 + "..."
    
    def test_human_readable_size(self):
        """Fayl hajmini formatlash"""
        result = HelperUtils.human_readable_size(1024)
        assert "KB" in result
    
    def test_mask_sensitive_info(self):
        """Maxfiy ma'lumotlarni yashirish"""
        result = HelperUtils.mask_sensitive_info("test@email.com")
        assert result != "test@email.com"
        assert "@" in result
