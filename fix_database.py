import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

print("🔄 Conectando a la base de datos...")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cur = conn.cursor()

try:
    print("🔄 Agregando restricción UNIQUE a la tabla puc...")
    cur.execute("ALTER TABLE puc ADD CONSTRAINT puc_codigo_unique UNIQUE (codigo);")
    conn.commit()
    print("✅ ¡Listo! La base de datos está corregida")
    print("Ahora puedes usar el botón 'Inicializar PUC Básico'")
except Exception as e:
    error_msg = str(e).lower()
    if "already exists" in error_msg or "duplicate" in error_msg:
        print("✓ La restricción ya existe, todo está bien")
    else:
        print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
