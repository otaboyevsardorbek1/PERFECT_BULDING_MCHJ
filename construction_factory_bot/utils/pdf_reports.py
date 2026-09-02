"""
PDF Hisobotlar - Qurilish Korxonasi uchun PDF hisobot yaratish moduli
reportlab kutubxonasi ishlatiladi
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime, date
import os
from typing import Dict, List, Any, Optional

from config import BASE_DIR

# PDF saqlash papkasi
PDF_REPORTS_DIR = BASE_DIR / "reports" / "pdf"
PDF_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class PDFReportGenerator:
    """PDF hisobot yaratuvchi klass"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Maxsus stillarni sozlash"""
        
        # Sarlavha stili
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_CENTER
        ))
        
        # Kichik sarlavha
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#34495E')
        ))
        
        # Matn stili
        self.styles.add(ParagraphStyle(
            name='CustomText',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            textColor=colors.HexColor('#2C3E50')
        ))
        
        # Jadvallar uchun
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER
        ))
    
    def _create_header(self, title: str, subtitle: str = None):
        """Sarlavha yaratish"""
        elements = []
        
        # Sarlavha
        elements.append(Paragraph(title, self.styles['CustomTitle']))
        
        # Sana
        elements.append(Paragraph(
            f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            self.styles['CustomText']
        ))
        
        if subtitle:
            elements.append(Paragraph(subtitle, self.styles['CustomText']))
        
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_table(self, headers: List[str], data: List[List], col_widths: List[float] = None):
        """Jadvallar yaratish"""
        
        # Ma'lumotlarni formatlash
        table_data = [headers] + data
        
        # Jadvallar yaratish
        table = Table(table_data, colWidths=col_widths)
        
        # Jadvallar stilini sozlash
        style = TableStyle([
            # Sarlavha qatori
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Ma'lumotlar qatorlari
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            
            # Chegaralar
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7')),
        ])
        
        # Juft qatorlar uchun stil (dinamik)
        for i in range(2, len(table_data), 2):
            style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#ECF0F1'))
        
        table.setStyle(style)
        
        return table
    
    def generate_warehouse_report(self, raw_materials: List[Dict], products: List[Dict], 
                                  filename: str = None) -> str:
        """
        Ombor holati bo'yicha PDF hisobot
        
        Args:
            raw_materials: Xom ashyo ma'lumotlari
            products: Mahsulotlar ma'lumotlari
            filename: Fayl nomi (agar berilmasa, avtomatik)
            
        Returns:
            str: PDF fayl yo'li
        """
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ombor_hisoboti_{timestamp}.pdf"
        
        filepath = os.path.join(PDF_REPORTS_DIR, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4, 
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        elements = []
        
        # Sarlavha
        elements.extend(self._create_header(
            "OMBOR HOLATI HISOBOTI",
            f"Davr: {date.today().strftime('%d.%m.%Y')}"
        ))
        
        # Umumiy statistika
        total_raw_value = sum(rm['current_stock'] * rm['price_per_unit'] for rm in raw_materials)
        total_products = len(products)
        
        elements.append(Paragraph(
            f"Umumiy xom ashyo qiymati: {total_raw_value:,.0f} so'm",
            self.styles['CustomText']
        ))
        elements.append(Paragraph(
            f"Tayyor mahsulotlar turi: {total_products} ta",
            self.styles['CustomText']
        ))
        elements.append(Spacer(1, 20))
        
        # Xom ashyolar jadvali
        elements.append(Paragraph("XOM ASHYOLAR", self.styles['CustomHeading']))
        
        rm_headers = ['№', 'Nomi', 'Birlik', 'Qoldiq', 'Min.', 'Narx', 'Qiymat', 'Holat']
        rm_data = []
        
        for idx, rm in enumerate(raw_materials, 1):
            value = rm['current_stock'] * rm['price_per_unit']
            status = "Yetarli" if rm['current_stock'] > rm['min_stock'] else "Yetarli emas"
            
            rm_data.append([
                str(idx),
                rm['name'],
                rm['unit'],
                f"{rm['current_stock']:,.0f}",
                f"{rm['min_stock']:,.0f}",
                f"{rm['price_per_unit']:,.0f}",
                f"{value:,.0f}",
                status
            ])
        
        rm_table = self._create_table(rm_headers, rm_data, 
                                       col_widths=[30, 80, 40, 60, 60, 60, 80, 70])
        elements.append(rm_table)
        elements.append(Spacer(1, 30))
        
        # Mahsulotlar jadvali
        elements.append(Paragraph("TAYYOR MAHSULOTLAR", self.styles['CustomHeading']))
        
        prod_headers = ['№', 'Nomi', 'Birlik', 'Sotish narxi', 'Xarajat', 'Foyda %']
        prod_data = []
        
        for idx, prod in enumerate(products, 1):
            profit_margin = ((prod['selling_price'] - prod['production_cost']) / 
                           prod['production_cost'] * 100) if prod['production_cost'] > 0 else 0
            
            prod_data.append([
                str(idx),
                prod['name'],
                prod['unit'],
                f"{prod['selling_price']:,.0f}",
                f"{prod['production_cost']:,.0f}",
                f"{profit_margin:.1f}%"
            ])
        
        prod_table = self._create_table(prod_headers, prod_data,
                                         col_widths=[30, 100, 50, 80, 80, 60])
        elements.append(prod_table)
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            f"Hisobot yaratilgan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            self.styles['CustomText']
        ))
        
        # PDF yaratish
        doc.build(elements)
        
        return filepath
    
    def generate_financial_report(self, financial_data: Dict, period: str,
                                  filename: str = None) -> str:
        """
        Moliya hisoboti PDF
        
        Args:
            financial_data: Moliyaviy ma'lumotlar
            period: Davr
            filename: Fayl nomi
            
        Returns:
            str: PDF fayl yo'li
        """
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"moliya_hisoboti_{period}_{timestamp}.pdf"
        
        filepath = os.path.join(PDF_REPORTS_DIR, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        elements = []
        
        # Sarlavha
        elements.extend(self._create_header(
            f"MOLIYA HISOBOTI - {period.upper()}",
            f"Davr: {date.today().strftime('%d.%m.%Y')}"
        ))
        
        # Daromadlar
        elements.append(Paragraph("DAROMADLAR", self.styles['CustomHeading']))
        
        income_data = [
            ['Sotuvdan daromad', f"{financial_data.get('total_sales_amount', 0):,.0f} so'm"],
            ['Boshqa daromadlar', f"{financial_data.get('other_income', 0):,.0f} so'm"],
            ['JAMI DAROMAD', f"{financial_data.get('total_sales_amount', 0) + financial_data.get('other_income', 0):,.0f} so'm"]
        ]
        
        income_table = self._create_table(['Ko\'rsatkich', 'Qiymat'], income_data,
                                           col_widths=[200, 150])
        elements.append(income_table)
        elements.append(Spacer(1, 20))
        
        # Xarajatlar
        elements.append(Paragraph("XARAJATLAR", self.styles['CustomHeading']))
        
        expense_data = [
            ['Ishlab chiqarish', f"{financial_data.get('production_costs', 0):,.0f} so'm"],
            ['Maosh to\'lovlari', f"{financial_data.get('salary_costs', 0):,.0f} so'm"],
            ['Kommunal', f"{financial_data.get('utility_costs', 0):,.0f} so'm"],
            ['Boshqa', f"{financial_data.get('other_expenses', 0):,.0f} so'm"],
            ['JAMI XARAJAT', f"{financial_data.get('total_costs', 0):,.0f} so'm"]
        ]
        
        expense_table = self._create_table(['Ko\'rsatkich', 'Qiymat'], expense_data,
                                            col_widths=[200, 150])
        elements.append(expense_table)
        elements.append(Spacer(1, 20))
        
        # Natija
        elements.append(Paragraph("NATIJALAR", self.styles['CustomHeading']))
        
        net_profit = financial_data.get('net_profit', 0)
        profit_margin = financial_data.get('profit_margin', 0)
        
        result_data = [
            ['Sof foyda', f"{net_profit:,.0f} so'm"],
            ['Foyda marjasi', f"{profit_margin:.1f}%"],
            ['Holat', "Yaxshi" if net_profit > 0 else "Zarar"]
        ]
        
        result_table = self._create_table(['Ko\'rsatkich', 'Qiymat'], result_data,
                                           col_widths=[200, 150])
        elements.append(result_table)
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            f"Hisobot yaratilgan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            self.styles['CustomText']
        ))
        
        doc.build(elements)
        
        return filepath
    
    def generate_production_report(self, orders: List[Dict], stats: Dict,
                                   filename: str = None) -> str:
        """
        Ishlab chiqarish hisoboti PDF
        
        Args:
            orders: Buyurtmalar ro'yxati
            stats: Statistika
            filename: Fayl nomi
            
        Returns:
            str: PDF fayl yo'li
        """
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ishlab_chiqarish_hisoboti_{timestamp}.pdf"
        
        filepath = os.path.join(PDF_REPORTS_DIR, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        elements = []
        
        # Sarlavha
        elements.extend(self._create_header(
            "ISHLAB CHIQARISH HISOBOTI",
            f"Umumiy buyurtmalar: {stats.get('total_orders', 0)} ta"
        ))
        
        # Statistika
        elements.append(Paragraph("UMUMIY KO'RSATKICHLAR", self.styles['CustomHeading']))
        
        stat_data = [
            ['Jami buyurtmalar', str(stats.get('total_orders', 0))],
            ['Bajarilgan', str(stats.get('completed_orders', 0))],
            ['Jami miqdor', f"{stats.get('total_quantity', 0)} birlik"],
            ['Jami xarajat', f"{stats.get('total_cost', 0):,.0f} so'm"],
            ['Jami daromad', f"{stats.get('total_revenue', 0):,.0f} so'm"],
            ['Sof foyda', f"{stats.get('total_profit', 0):,.0f} so'm"],
        ]
        
        stat_table = self._create_table(['Ko\'rsatkich', 'Qiymat'], stat_data,
                                         col_widths=[200, 150])
        elements.append(stat_table)
        elements.append(Spacer(1, 20))
        
        # Buyurtmalar jadvali
        if orders:
            elements.append(Paragraph("BUYURTMALAR RO'YXATI", self.styles['CustomHeading']))
            
            order_headers = ['№', 'Mahsulot', 'Miqdor', 'Xarajat', 'Holat']
            order_data = []
            
            for idx, order in enumerate(orders[:20], 1):  # Faqat 20 ta
                order_data.append([
                    str(idx),
                    order.get('product_name', 'Noma\'lum'),
                    str(order.get('quantity', 0)),
                    f"{order.get('total_cost', 0):,.0f}",
                    order.get('status', 'jarayonda')
                ])
            
            order_table = self._create_table(order_headers, order_data,
                                              col_widths=[30, 120, 60, 80, 80])
            elements.append(order_table)
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            f"Hisobot yaratilgan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            self.styles['CustomText']
        ))
        
        doc.build(elements)
        
        return filepath
    
    def generate_employee_report(self, employees: List[Dict], stats: Dict,
                                 filename: str = None) -> str:
        """
        Xodimlar hisoboti PDF
        
        Args:
            employees: Xodimlar ro'yxati
            stats: Statistika
            filename: Fayl nomi
            
        Returns:
            str: PDF fayl yo'li
        """
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"xodimlar_hisoboti_{timestamp}.pdf"
        
        filepath = os.path.join(PDF_REPORTS_DIR, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        elements = []
        
        # Sarlavha
        elements.extend(self._create_header(
            "XODIMLAR HISOBOTI",
            f"Jami xodimlar: {len(employees)} kishi"
        ))
        
        # Statistika
        elements.append(Paragraph("UMUMIY STATISTIKA", self.styles['CustomHeading']))
        
        stat_data = [
            ['Jami xodimlar', str(len(employees))],
            ['O\'rtacha maosh', f"{stats.get('avg_salary', 0):,.0f} so'm"],
            ['Jami maosh xarajati', f"{stats.get('total_salary', 0):,.0f} so'm"],
        ]
        
        stat_table = self._create_table(['Ko\'rsatkich', 'Qiymat'], stat_data,
                                         col_widths=[200, 150])
        elements.append(stat_table)
        elements.append(Spacer(1, 20))
        
        # Xodimlar jadvali
        elements.append(Paragraph("XODIMLAR RO'YXATI", self.styles['CustomHeading']))
        
        emp_headers = ['№', 'F.I.Sh', 'Lavozim', 'Bo\'lim', 'Maosh']
        emp_data = []
        
        for idx, emp in enumerate(employees, 1):
            emp_data.append([
                str(idx),
                emp.get('full_name', 'Noma\'lum'),
                emp.get('position', 'Noma\'lum'),
                emp.get('department', 'Noma\'lum'),
                f"{emp.get('salary', 0):,.0f}"
            ])
        
        emp_table = self._create_table(emp_headers, emp_data,
                                        col_widths=[30, 120, 80, 80, 80])
        elements.append(emp_table)
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            f"Hisobot yaratilgan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            self.styles['CustomText']
        ))
        
        doc.build(elements)
        
        return filepath


# Global instance
pdf_generator = PDFReportGenerator()
