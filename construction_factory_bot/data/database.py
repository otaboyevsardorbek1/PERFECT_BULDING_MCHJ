import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

class DatabaseManager:
    def __init__(self, db_path: str = "construction.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.init_default_data()
    
    def create_tables(self):
        # Xom ashyolar jadvali
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            unit TEXT NOT NULL,
            current_stock REAL DEFAULT 0,
            min_stock REAL DEFAULT 0,
            price_per_unit REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Mahsulotlar jadvali
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            unit TEXT NOT NULL,
            selling_price REAL DEFAULT 0,
            production_cost REAL DEFAULT 0,
            profit_margin REAL DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Formulalar jadvali
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS formulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            raw_material_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id)
        )
        ''')
        
        # Ombordagi harakatlar
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouse_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            product_id INTEGER,
            raw_material_id INTEGER,
            quantity REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id)
        )
        ''')
        
        # Ishlab chiqarish buyurtmalari
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            total_cost REAL DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_date TIMESTAMP,
            created_by INTEGER,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        ''')
        
        self.conn.commit()
    
    def init_default_data(self):
        # Boshlang'ich xom ashyo turlari
        raw_materials = [
            ("Klinker", "kg", 10000, 1000, 500),
            ("Gips", "kg", 5000, 500, 300),
            ("Qum", "kg", 20000, 2000, 50),
            ("Shag'al", "kg", 15000, 1500, 80),
            ("Temir sutka", "kg", 8000, 800, 2000),
            ("Gil", "kg", 10000, 1000, 150),
            ("Kvart qumi", "kg", 6000, 600, 400),
            ("Plastik", "kg", 3000, 300, 1200),
            ("Kimyoviy moddalar", "kg", 2000, 200, 2500),
            ("Oksir", "kg", 1000, 100, 800),
            ("Rang beruvchi", "kg", 500, 50, 5000),
            ("Kleb", "kg", 3000, 300, 1200)
        ]
        
        for material in raw_materials:
            self.cursor.execute('''
            INSERT OR IGNORE INTO raw_materials (name, unit, current_stock, min_stock, price_per_unit)
            VALUES (?, ?, ?, ?, ?)
            ''', material)
        
        # Boshlang'ich mahsulotlar
        products = [
            ("Sement M500", "sement", "qop", 12000, 7000, 40),
            ("Rodbin 12mm", "armatura", "metr", 4500, 3200, 35),
            ("Kafel 30x30", "kafel", "dona", 850, 450, 50),
            ("Nalinoy pol", "pol", "m2", 2800, 1800, 45),
            ("Gips qop 25kg", "gips", "qop", 3500, 2200, 40),
            ("Keramika plitka", "plitka", "dona", 1200, 800, 55),
            ("Beton M300", "beton", "m3", 550000, 450000, 30)
        ]
        
        for product in products:
            self.cursor.execute('''
            INSERT OR IGNORE INTO products (name, category, unit, selling_price, production_cost, profit_margin)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', product)
        
        # Sement formulasi
        self.cursor.execute("SELECT id FROM products WHERE name='Sement M500'")
        cement_id = self.cursor.fetchone()[0]
        
        formula_data = [
            (cement_id, 1, 45),  # 45kg Klinker
            (cement_id, 2, 5),   # 5kg Gips
        ]
        
        for formula in formula_data:
            self.cursor.execute('''
            INSERT OR IGNORE INTO formulas (product_id, raw_material_id, quantity)
            VALUES (?, ?, ?)
            ''', formula)
        
        self.conn.commit()