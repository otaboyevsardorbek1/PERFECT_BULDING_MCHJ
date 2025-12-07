import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.initialize_data()
    
    def create_tables(self):
        """Ma'lumotlar bazasi jadvallarini yaratish"""
        
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
            unit TEXT NOT NULL,
            selling_price REAL DEFAULT 0,
            production_cost REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Mahsulot formulalari jadvali
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_formulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            raw_material_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id),
            UNIQUE(product_id, raw_material_id)
        )
        ''')
        
        # Ombordagi harakatlar jadvali
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouse_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            product_id INTEGER,
            raw_material_id INTEGER,
            quantity REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            user_id INTEGER,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id)
        )
        ''')
        
        # Ishlab chiqarish buyurtmalari jadvali
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT DEFAULT 'jarayonda',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_date TIMESTAMP,
            total_cost REAL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        ''')
        
        self.conn.commit()
        logger.info("Database tables created successfully")
    
    def initialize_data(self):
        """Boshlang'ich ma'lumotlarni kiritish"""
        
        # Xom ashyo turlari
        raw_materials = [
            ("Klinker", "kg", 10000, 1000, 500),
            ("Gips", "kg", 5000, 500, 300),
            ("Qum", "kg", 20000, 2000, 50),
            ("Shag'al", "kg", 15000, 1500, 80),
            ("Temir", "kg", 8000, 800, 2000),
            ("Gil", "kg", 10000, 1000, 150),
            ("Kvart qumi", "kg", 6000, 600, 400),
            ("Plastik", "kg", 3000, 300, 1200),
            ("Kimyoviy moddalar", "kg", 2000, 200, 2500),
            ("Oksir", "kg", 1000, 100, 800)
        ]
        
        for material in raw_materials:
            self.cursor.execute('''
            INSERT OR IGNORE INTO raw_materials (name, unit, current_stock, min_stock, price_per_unit)
            VALUES (?, ?, ?, ?, ?)
            ''', material)
        
        # Mahsulotlar
        products = [
            ("Sement M500 (50kg)", "qop", 12000, 7000),
            ("Rodbin 12mm", "metr", 4500, 3200),
            ("Kafel 30x30", "dona", 850, 450),
            ("Nalinoy pol", "m2", 2800, 1800),
            ("Gips", "qop", 3500, 2200),
            ("Keramika plitka", "dona", 1200, 800)
        ]
        
        for product in products:
            self.cursor.execute('''
            INSERT OR IGNORE INTO products (name, unit, selling_price, production_cost)
            VALUES (?, ?, ?, ?)
            ''', product)
        
        # Sement formulasi
        self.cursor.execute('SELECT id FROM products WHERE name = "Sement M500 (50kg)"')
        cement_id = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT id FROM raw_materials WHERE name = "Klinker"')
        klinker_id = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT id FROM raw_materials WHERE name = "Gips"')
        gips_id = self.cursor.fetchone()[0]
        
        # Formulani kiritish
        formulas = [
            (cement_id, klinker_id, 45),  # 45kg klinker
            (cement_id, gips_id, 5),      # 5kg gips
        ]
        
        for formula in formulas:
            self.cursor.execute('''
            INSERT OR IGNORE INTO product_formulas (product_id, raw_material_id, quantity)
            VALUES (?, ?, ?)
            ''', formula)
        
        self.conn.commit()
        logger.info("Initial data inserted successfully")
    
    def get_warehouse_status(self):
        """Ombordagi holatni olish"""
        self.cursor.execute('''
        SELECT 
            rm.name as material_name,
            rm.unit,
            rm.current_stock,
            rm.min_stock,
            rm.price_per_unit,
            CASE 
                WHEN rm.current_stock < rm.min_stock THEN '⚠️ Yetarli emas'
                WHEN rm.current_stock < rm.min_stock * 1.5 THEN '⚠️ Ozgina'
                ELSE '✅ Yetarli'
            END as status
        FROM raw_materials rm
        ORDER BY status, rm.name
        ''')
        return self.cursor.fetchall()
    
    def get_products_status(self):
        """Tayyor mahsulotlar holati"""
        self.cursor.execute('''
        SELECT 
            p.name,
            p.unit,
            p.selling_price,
            p.production_cost,
            (SELECT SUM(quantity) FROM warehouse_transactions 
             WHERE product_id = p.id AND transaction_type = 'ishlab_chiqarish') as produced,
            (SELECT SUM(quantity) FROM warehouse_transactions 
             WHERE product_id = p.id AND transaction_type = 'sotish') as sold
        FROM products p
        ''')
        return self.cursor.fetchall()
    
    def add_transaction(self, product_id, raw_material_id, quantity, transaction_type, user_id, notes=""):
        """Ombordagi harakatni kiritish"""
        self.cursor.execute('''
        INSERT INTO warehouse_transactions 
        (product_id, raw_material_id, quantity, transaction_type, user_id, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (product_id, raw_material_id, quantity, transaction_type, user_id, notes))
        
        # Agar xom ashyo chiqimi bo'lsa, stock ni yangilash
        if raw_material_id and transaction_type == 'ishlab_chiqarish':
            self.cursor.execute('''
            UPDATE raw_materials 
            SET current_stock = current_stock - ?
            WHERE id = ?
            ''', (quantity, raw_material_id))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def close(self):
        """Database ulanishini yopish"""
        self.conn.close()

db = Database()