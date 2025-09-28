
import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), "pollos.db")

def get_conn():
    return sqlite3.connect(DB)

def init_db(seed=True):
    conn = get_conn()
    c = conn.cursor()
    # users table (for simple login)
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )""")
    # products (inventory)
    c.execute("""CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        stock REAL DEFAULT 0,
        costo REAL DEFAULT 0,
        valor_total REAL DEFAULT 0
    )""")
    # clients
    c.execute("""CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE
    )""")
    # invoices header
    c.execute("""CREATE TABLE IF NOT EXISTS facturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        cliente TEXT,
        fecha TEXT,
        factura_num INTEGER UNIQUE,
        total REAL
    )""")
    # invoice lines
    c.execute("""CREATE TABLE IF NOT EXISTS detalle_facturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        factura_id INTEGER,
        producto_id INTEGER,
        producto TEXT,
        cantidad REAL,
        precio REAL,
        total REAL
    )""")
    # diario contable
    c.execute("""CREATE TABLE IF NOT EXISTS diario_contable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        documento TEXT,
        codigo TEXT,
        cuenta TEXT,
        debe REAL,
        haber REAL,
        descripcion TEXT
    )""")
    conn.commit()

    if seed:
        # seed admin user if not exists
        c.execute("SELECT COUNT(*) FROM usuarios")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO usuarios (username, password) VALUES (?,?)", ("admin","1234"))
        # seed products if none
        c.execute("SELECT COUNT(*) FROM productos")
        if c.fetchone()[0] == 0:
            productos = [
                ("Pollo Entero", 100, 5.00, 100*5.00),
                ("Pechuga (kg)", 50, 4.50, 50*4.50),
                ("Alitas (kg)", 30, 3.20, 30*3.20)
            ]
            c.executemany("INSERT OR IGNORE INTO productos (nombre, stock, costo, valor_total) VALUES (?,?,?,?)", productos)
        # seed a client
        c.execute("SELECT COUNT(*) FROM clientes")
        if c.fetchone()[0] == 0:
            c.execute("INSERT OR IGNORE INTO clientes (nombre) VALUES (?)", ("Cliente General",))
    conn.commit()
    conn.close()
