import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # GUI o'rnatmaslik uchun
import seaborn as sns
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
from typing import List, Dict, Any, Tuple
from config import CHARTS_DIR

# Matplotlib sozlamalari
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

def create_stock_chart(raw_materials: List[Dict]) -> str:
    """Xom ashyo qoldiqlari grafigi"""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # 1. Bar chart - eng ko'p va eng kam qoldiqlar
    names = [m['name'][:15] + "..." if len(m['name']) > 15 else m['name'] for m in raw_materials]
    stocks = [m['current_stock'] for m in raw_materials]
    min_stocks = [m['min_stock'] for m in raw_materials]
    
    x = np.arange(len(names))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, stocks, width, label='Jami qoldiq', color='skyblue')
    bars2 = ax1.bar(x + width/2, min_stocks, width, label='Minimal qoldiq', color='lightcoral')
    
    ax1.set_xlabel('Xom ashyolar')
    ax1.set_ylabel('Miqdor')
    ax1.set_title('Xom ashyo qoldiqlari')
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, rotation=45, ha='right')
    ax1.legend()
    
    # Qo'shimcha: Qizil chiziq - minimal qoldiq
    for bar1, bar2 in zip(bars1, bars2):
        if bar1.get_height() < bar2.get_height():
            bar1.set_color('red')
    
    # 2. Pie chart - qiymat bo'yicha taqsimot
    values = [m['current_stock'] * m['price_per_unit'] for m in raw_materials]
    total_value = sum(values)
    
    # Faqat 0 dan katta qiymatlarga ega bo'lganlarni olish
    pie_data = [(names[i], values[i]) for i in range(len(values)) if values[i] > 0]
    pie_names = [d[0] for d in pie_data]
    pie_values = [d[1] for d in pie_data]
    
    if pie_values:
        wedges, texts, autotexts = ax2.pie(
            pie_values, 
            labels=pie_names, 
            autopct=lambda pct: f'{pct:.1f}%\n({int(pct/100.*sum(pie_values)):,} so\'m)',
            startangle=90,
            textprops={'fontsize': 8}
        )
        ax2.set_title(f'Xom ashyo qiymati taqsimoti\nJami: {total_value:,.0f} so\'m')
    
    plt.tight_layout()
    
    # Grafikni saqlash
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stock_chart_{timestamp}.png"
    filepath = os.path.join(CHARTS_DIR, filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    
    return filepath

def create_production_chart(production_data: List[Dict]) -> str:
    """Ishlab chiqarish statistikasi grafigi"""
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # Ma'lumotlarni tayyorlash
    df = pd.DataFrame(production_data)
    
    if not df.empty:
        # 1. Mahsulotlar bo'yicha ishlab chiqarish
        product_counts = df['product_name'].value_counts()
        ax1.bar(product_counts.index, product_counts.values, color='teal')
        ax1.set_title('Mahsulotlar bo\'yicha ishlab chiqarish')
        ax1.set_xlabel('Mahsulotlar')
        ax1.set_ylabel('Miqdor')
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. Kunlik ishlab chiqarish trendi
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            daily_production = df.groupby(df['date'].dt.date)['quantity'].sum()
            ax2.plot(daily_production.index, daily_production.values, marker='o', linewidth=2)
            ax2.set_title('Kunlik ishlab chiqarish trendi')
            ax2.set_xlabel('Sana')
            ax2.set_ylabel('Miqdor')
            ax2.grid(True, alpha=0.3)
        
        # 3. Xarajat va daromad taqqoslash
        if all(col in df.columns for col in ['total_cost', 'total_revenue']):
            costs = df['total_cost'].sum()
            revenues = df['total_revenue'].sum()
            profit = revenues - costs
            
            bars = ax3.bar(['Xarajat', 'Daromad', 'Foyda'], 
                          [costs, revenues, profit],
                          color=['red', 'green', 'blue'])
            ax3.set_title('Xarajat, Daromad va Foyda')
            ax3.set_ylabel('So\'m')
            
            # Qiymatlarni grafik ustiga chiqarish
            for bar in bars:
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                        f'{height:,.0f}',
                        ha='center', va='bottom')
        
        # 4. Foyda marjasini ko'rsatish
        if 'profit_margin' in df.columns:
            profit_margins = df['profit_margin']
            ax4.hist(profit_margins, bins=10, edgecolor='black', alpha=0.7)
            ax4.set_title('Foyda marjasi taqsimoti')
            ax4.set_xlabel('Foyda marjasi (%)')
            ax4.set_ylabel('Soni')
            ax4.axvline(x=profit_margins.mean(), color='red', linestyle='--', label=f'O\'rtacha: {profit_margins.mean():.1f}%')
            ax4.legend()
    
    plt.suptitle('Ishlab Chiqarish Statistikasi', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    # Grafikni saqlash
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"production_chart_{timestamp}.png"
    filepath = os.path.join(CHARTS_DIR, filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    
    return filepath

def create_financial_chart(financial_data: Dict, period: str) -> str:
    """Moliya statistikasi grafigi"""
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Daromad va xarajatlar taqqoslash
    categories = ['Sotuv', 'Ishlab chiqarish', 'Maosh', 'Kommunal', 'Boshqa']
    income = [financial_data.get('sales_income', 0), 0, 0, 0, financial_data.get('other_income', 0)]
    expenses = [0, financial_data.get('production_costs', 0), 
                financial_data.get('salary_costs', 0),
                financial_data.get('utility_costs', 0),
                financial_data.get('other_expenses', 0)]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, income, width, label='Daromad', color='green')
    bars2 = ax1.bar(x + width/2, expenses, width, label='Xarajat', color='red')
    
    ax1.set_xlabel('Kategoriyalar')
    ax1.set_ylabel('So\'m')
    ax1.set_title('Daromad va Xarajatlar')
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories)
    ax1.legend()
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. Foyda dinamikasi (oylik)
    if 'monthly_profit' in financial_data:
        months = list(financial_data['monthly_profit'].keys())
        profits = list(financial_data['monthly_profit'].values())
        
        colors = ['green' if p >= 0 else 'red' for p in profits]
        bars = ax2.bar(months, profits, color=colors)
        ax2.set_title('Oylik foyda dinamikasi')
        ax2.set_xlabel('Oy')
        ax2.set_ylabel('Foyda (so\'m)')
        ax2.axhline(y=0, color='black', linewidth=0.8)
        
        # Qiymatlarni ustiga yozish
        for bar in bars:
            height = bar.get_height()
            va = 'bottom' if height >= 0 else 'top'
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:,.0f}',
                    ha='center', va=va)
    
    # 3. Xarajatlar tarkibi
    expense_labels = ['Ishlab chiqarish', 'Maosh', 'Kommunal', 'Boshqa']
    expense_values = [
        financial_data.get('production_costs', 0),
        financial_data.get('salary_costs', 0),
        financial_data.get('utility_costs', 0),
        financial_data.get('other_expenses', 0)
    ]
    
    # Faqat 0 dan katta qiymatlarga ega bo'lganlar
    pie_labels = [expense_labels[i] for i in range(len(expense_values)) if expense_values[i] > 0]
    pie_values = [v for v in expense_values if v > 0]
    
    if pie_values:
        wedges, texts, autotexts = ax3.pie(
            pie_values, 
            labels=pie_labels, 
            autopct=lambda pct: f'{pct:.1f}%',
            startangle=90
        )
        ax3.set_title('Xarajatlar tarkibi')
    
    # 4. Foyda marjasi
    profit_margin = financial_data.get('profit_margin', 0)
    
    # Progress bar ko'rinishida
    ax4.barh([0], [100], color='lightgray', height=0.5)
    ax4.barh([0], [profit_margin], color='green' if profit_margin >= 20 else 'orange' if profit_margin >= 10 else 'red', height=0.5)
    ax4.set_xlim(0, 100)
    ax4.set_yticks([])
    ax4.set_title(f'Foyda Marjasi: {profit_margin:.1f}%')
    ax4.text(profit_margin/2, 0, f'{profit_margin:.1f}%', 
            ha='center', va='center', color='white', fontweight='bold')
    
    plt.suptitle(f'Moliya Statistikasi - {period.upper()}', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    # Grafikni saqlash
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"financial_chart_{period}_{timestamp}.png"
    filepath = os.path.join(CHARTS_DIR, filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    
    return filepath

def create_employee_chart(employees: List[Dict], work_data: Dict) -> str:
    """Xodimlar statistikasi grafigi"""
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Lavozimlar bo'yicha xodimlar soni
    positions = {}
    for emp in employees:
        pos = emp['position']
        positions[pos] = positions.get(pos, 0) + 1
    
    if positions:
        ax1.bar(positions.keys(), positions.values(), color='steelblue')
        ax1.set_title('Lavozimlar bo\'yicha xodimlar soni')
        ax1.set_xlabel('Lavozim')
        ax1.set_ylabel('Xodimlar soni')
        ax1.tick_params(axis='x', rotation=45)
    
    # 2. O'rtacha maosh taqqoslash
    if 'avg_salary_by_position' in work_data:
        avg_salaries = work_data['avg_salary_by_position']
        ax2.bar(avg_salaries.keys(), avg_salaries.values(), color='darkorange')
        ax2.set_title('Lavozimlar bo\'yicha o\'rtacha maosh')
        ax2.set_xlabel('Lavozim')
        ax2.set_ylabel('O\'rtacha maosh (so\'m)')
        ax2.tick_params(axis='x', rotation=45)
        
        # Format numbers
        ax2.get_yaxis().set_major_formatter(
            plt.FuncFormatter(lambda x, p: format(int(x), ','))
        )
    
    # 3. Ish vaqti statistikasi
    if 'work_hours_stats' in work_data:
        stats = work_data['work_hours_stats']
        labels = ['O\'rtacha ish soati', 'Qo\'shimcha ish', 'Dam olish']
        values = [stats.get('avg_hours', 0), stats.get('overtime', 0), stats.get('time_off', 0)]
        
        ax3.bar(labels, values, color=['blue', 'red', 'green'])
        ax3.set_title('Ish vaqti statistikasi')
        ax3.set_ylabel('Soat')
    
    # 4. Xodimlarning holati
    status_counts = {}
    for emp in employees:
        status = emp['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    if status_counts:
        colors = {'faol': 'green', 'ta\'tilda': 'yellow', 'ishdan_bo\'shatilgan': 'red'}
        status_colors = [colors.get(status, 'gray') for status in status_counts.keys()]
        
        wedges, texts, autotexts = ax4.pie(
            status_counts.values(), 
            labels=status_counts.keys(), 
            colors=status_colors,
            autopct='%1.1f%%',
            startangle=90
        )
        ax4.set_title('Xodimlarning holati')
    
    plt.suptitle('Xodimlar Statistikasi', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    # Grafikni saqlash
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"employee_chart_{timestamp}.png"
    filepath = os.path.join(CHARTS_DIR, filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    
    return filepath