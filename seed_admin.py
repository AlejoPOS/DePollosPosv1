# seed_admin.py
import sqlite3
from werkzeug.security import generate_password_hash

DB = "pos.db"

def seed_admin():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE NOT NULL, clave TEXT NOT NULL, rol TEXT CHECK(rol IN ('admin','cajero','auxiliar')) NOT NULL DEFAULT 'cajero', activo INTEGER DEFAULT 1)")
    hashed = generate_password_hash("1234")
    try:
        cur.execute("INSERT OR IGNORE INTO usuarios (usuario, clave, rol, activo) VALUES (?, ?, ?, ?)", ("admin", hashed, "admin", 1))
        conn.commit()
        print("✅ Usuario admin creado (usuario=admin, clave=1234). Cambia la clave después.")
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    seed_admin()
