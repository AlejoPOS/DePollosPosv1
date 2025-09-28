import os
import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]

schema = """
-- ===========================
-- TERCEROS (Clientes / Proveedores)
-- ===========================
CREATE TABLE IF NOT EXISTS terceros (
    id SERIAL PRIMARY KEY,
    nombres TEXT NOT NULL,
    apellidos TEXT,
    telefono TEXT,
    correo TEXT,
    direccion TEXT,
    tipo TEXT NOT NULL CHECK(tipo IN ('Cliente', 'Proveedor'))
);

-- ===========================
-- INVENTARIO
-- ===========================
CREATE TABLE IF NOT EXISTS productos (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    costo REAL NOT NULL,
    precio REAL NOT NULL,
    stock REAL NOT NULL DEFAULT 0,
    unidad TEXT DEFAULT 'UND'
);

-- ===========================
-- FACTURACIÓN (VENTAS)
-- ===========================
CREATE TABLE IF NOT EXISTS facturas (
    id SERIAL PRIMARY KEY,
    tercero_id INTEGER REFERENCES terceros(id),
    numero INTEGER NOT NULL,
    fecha DATE NOT NULL,
    total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS detalle_factura (
    id SERIAL PRIMARY KEY,
    factura_id INTEGER REFERENCES facturas(id),
    producto_id INTEGER REFERENCES productos(id),
    cantidad REAL NOT NULL,
    precio REAL NOT NULL,
    total REAL NOT NULL
);

-- ===========================
-- COMPRAS
-- ===========================
CREATE TABLE IF NOT EXISTS compras (
    id SERIAL PRIMARY KEY,
    tercero_id INTEGER REFERENCES terceros(id),
    numero TEXT,
    fecha DATE NOT NULL,
    total REAL NOT NULL,
    forma_pago TEXT CHECK(forma_pago IN ('contado','credito','transferencia')) NOT NULL,
    pagada BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS detalle_compra (
    id SERIAL PRIMARY KEY,
    compra_id INTEGER REFERENCES compras(id),
    producto_id INTEGER REFERENCES productos(id),
    cantidad REAL NOT NULL,
    costo REAL NOT NULL,
    total REAL NOT NULL
);

-- ===========================
-- GASTOS / INGRESOS
-- ===========================
CREATE TABLE IF NOT EXISTS gastos (
    id SERIAL PRIMARY KEY,
    descripcion TEXT NOT NULL,
    monto REAL NOT NULL,
    fecha DATE NOT NULL,
    tipo TEXT CHECK(tipo IN ('gasto','ingreso')) NOT NULL
);

-- ===========================
-- CONTABILIDAD
-- ===========================
CREATE TABLE IF NOT EXISTS puc (
    id SERIAL PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    tipo TEXT CHECK(tipo IN ('activo','pasivo','patrimonio','ingreso','gasto')) NOT NULL
);

CREATE TABLE IF NOT EXISTS movimientos_contables (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    cuenta_id INTEGER REFERENCES puc(id),
    descripcion TEXT,
    debito REAL DEFAULT 0,
    credito REAL DEFAULT 0,
    modulo TEXT,
    referencia_id INTEGER
);

-- ===========================
-- RECIBOS DE CAJA
-- ===========================
CREATE TABLE IF NOT EXISTS recibos_caja (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL,
    fecha DATE NOT NULL,
    tercero_id INTEGER REFERENCES terceros(id),
    concepto TEXT,
    valor REAL NOT NULL
);

-- ===========================
-- COMPROBANTES DE EGRESO
-- ===========================
CREATE TABLE IF NOT EXISTS comprobantes_egreso (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL,
    fecha DATE NOT NULL,
    tercero_id INTEGER REFERENCES terceros(id),
    concepto TEXT,
    valor REAL NOT NULL
);

-- ===========================
-- NOTAS DE CRÉDITO
-- ===========================
CREATE TABLE IF NOT EXISTS notas_credito (
    id SERIAL PRIMARY KEY,
    factura_id INTEGER REFERENCES facturas(id),
    numero INTEGER NOT NULL,
    fecha DATE NOT NULL,
    tercero_id INTEGER REFERENCES terceros(id),
    motivo TEXT,
    total REAL NOT NULL,
    creado_por TEXT
);

CREATE TABLE IF NOT EXISTS detalle_nota_credito (
    id SERIAL PRIMARY KEY,
    nota_id INTEGER REFERENCES notas_credito(id),
    producto_id INTEGER REFERENCES productos(id),
    descripcion TEXT,
    cantidad REAL,
    precio REAL,
    total REAL
);

-- ===========================
-- TRANSFORMACIONES
-- ===========================
CREATE TABLE IF NOT EXISTS transformaciones (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL,
    fecha DATE NOT NULL,
    descripcion TEXT,
    total_salida REAL DEFAULT 0,
    total_entrada REAL DEFAULT 0,
    creado_por TEXT
);

CREATE TABLE IF NOT EXISTS detalle_transformacion (
    id SERIAL PRIMARY KEY,
    transformacion_id INTEGER REFERENCES transformaciones(id),
    tipo TEXT CHECK(tipo IN ('salida','entrada')) NOT NULL,
    producto_id INTEGER REFERENCES productos(id),
    cantidad REAL NOT NULL,
    costo REAL NOT NULL,
    total REAL NOT NULL
);

-- ===========================
-- USUARIOS
-- ===========================
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    usuario TEXT UNIQUE NOT NULL,
    clave TEXT NOT NULL,
    rol TEXT CHECK(rol IN ('admin','cajero','auxiliar')) NOT NULL DEFAULT 'cajero',
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS permisos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    modulo TEXT NOT NULL,
    puede_ver BOOLEAN DEFAULT TRUE,
    puede_crear BOOLEAN DEFAULT FALSE,
    puede_editar BOOLEAN DEFAULT FALSE,
    puede_borrar BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS configuracion (
    id SERIAL PRIMARY KEY,
    clave TEXT NOT NULL UNIQUE,
    valor TEXT
);
"""

def init_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()
    cur.execute(schema)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Base de datos inicializada en PostgreSQL")

if __name__ == "__main__":
    init_db()
