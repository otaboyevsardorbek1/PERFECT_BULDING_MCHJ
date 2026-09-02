"""
SMS Xizmati - Eskiz.uz orqali SMS yuborish moduli
"""

import aiohttp
import logging
from typing import Dict, List, Optional
from datetime import datetime

from config import INTEGRATION_SETTINGS

logger = logging.getLogger(__name__)


class EskizSMSService:
    """Eskiz.uz SMS xizmati"""
    
    BASE_URL = "https://api.eskiz.uz"
    
    def __init__(self):
        self.api_key = INTEGRATION_SETTINGS.get('sms_api_key', '')
        self.sender = INTEGRATION_SETTINGS.get('sms_sender', 'KORXONA')
        self.token = None
        self.token_expires = None
    
    async def _get_token(self) -> Optional[str]:
        """SMS API token olish"""
        
        if self.token and self.token_expires:
            if datetime.utcnow() < self.token_expires:
                return self.token
        
        if not self.api_key:
            logger.error("SMS API key not configured")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/auth/login",
                    json={"email": self.api_key}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.token = data.get('data', {}).get('token')
                        logger.info("SMS token obtained successfully")
                        return self.token
                    else:
                        logger.error(f"Failed to get SMS token: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting SMS token: {e}")
            return None
    
    async def send_sms(self, phone_number: str, message: str) -> Dict:
        """
        SMS yuborish
        
        Args:
            phone_number: Telefon raqami (+998901234567)
            message: SMS matni
            
        Returns:
            Dict: Natija
        """
        
        if not INTEGRATION_SETTINGS.get('sms_enabled', False):
            return {
                'success': False,
                'error': 'SMS xizmati o\'chirilgan'
            }
        
        token = await self._get_token()
        if not token:
            return {
                'success': False,
                'error': 'SMS token olinmadi'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/message/sms/send",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "mobile_phone": phone_number,
                        "message": message,
                        "from": self.sender
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"SMS sent to {phone_number}")
                        return {
                            'success': True,
                            'data': data
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"SMS send failed: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f'HTTP {response.status}'
                        }
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def send_bulk_sms(self, phone_numbers: List[str], message: str) -> Dict:
        """
        Ommaviy SMS yuborish
        
        Args:
            phone_numbers: Telefon raqamlar ro'yxati
            message: SMS matni
            
        Returns:
            Dict: Natija
        """
        
        results = {
            'success': 0,
            'failed': 0,
            'total': len(phone_numbers)
        }
        
        for phone in phone_numbers:
            result = await self.send_sms(phone, message)
            if result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    async def send_low_stock_alert(self, material_name: str, current_stock: float, 
                                   min_stock: float, phone_numbers: List[str]) -> Dict:
        """
        Xom ashyo tugashi haqida SMS yuborish
        
        Args:
            material_name: Material nomi
            current_stock: Joriy qoldiq
            min_stock: Minimal qoldiq
            phone_numbers: Telefon raqamlar
            
        Returns:
            Dict: Natija
        """
        
        message = (
            f"⚠️ OGOHLANTIRISH!\n\n"
            f"{material_name} xom ashyosi tugab qolmoqda!\n"
            f"Joriy qoldiq: {current_stock} kg\n"
            f"Minimal qoldiq: {min_stock} kg\n\n"
            f"Tez orada to'ldirishni rejalashtiring!"
        )
        
        return await self.send_bulk_sms(phone_numbers, message)
    
    async def send_production_complete(self, product_name: str, quantity: int,
                                       phone_numbers: List[str]) -> Dict:
        """
        Ishlab chiqarish tugagani haqida SMS yuborish
        
        Args:
            product_name: Mahsulot nomi
            quantity: Miqdor
            phone_numbers: Telefon raqamlar
            
        Returns:
            Dict: Natija
        """
        
        message = (
            f"✅ ISHLAB CHIQARISH TUGADI!\n\n"
            f"Mahsulot: {product_name}\n"
            f"Miqdor: {quantity} birlik\n"
            f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Mahsulotlar omborga qo'shildi."
        )
        
        return await self.send_bulk_sms(phone_numbers, message)
    
    async def send_salary_reminder(self, employee_name: str, amount: float,
                                   phone_number: str) -> Dict:
        """
        Maosh eslatmasi SMS
        
        Args:
            employee_name: Xodim nomi
            amount: Maosh miqdori
            phone_number: Telefon raqami
            
        Returns:
            Dict: Natija
        """
        
        message = (
            f"💰 MAOSH TO'LOVI\n\n"
            f"Hurmatli {employee_name}!\n"
            f"Sizning maoshingiz: {amount:,.0f} so'm\n"
            f"To'lov amalga oshirildi.\n\n"
            f"Xodimlar bo'limidan olishingiz mumkin."
        )
        
        return await self.send_sms(phone_number, message)


# Global instance
sms_service = EskizSMSService()
