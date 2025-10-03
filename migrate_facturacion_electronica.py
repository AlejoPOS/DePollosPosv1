#!/usr/bin/env python3
"""
Migración para Facturación Electrónica DIAN
Añade campos obligatorios según Resolución 000165 (01/NOV/2023)
"""
import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

def migrate():
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()
    
    try:
        print("🔄 Iniciando migración para Facturación Electrónica DIAN...")
        
        # ==========================================
        # 1. CONFIGURACIÓN DE LA EMPRESA (EMISOR)
        # ==========================================
        print("\n📋 Añadiendo configuración de empresa...")
        
        config_empresa = [
            ("empresa_tipo_identificacion", "31"),  # 31 = NIT
            ("empresa_digito_verificacion", ""),
            ("empresa_regimen", "49"),  # 49 = Régimen Simple
            ("empresa_responsabilidad_fiscal", "O-13;O-15;O-23"),  # Gran contribuyente, Autorretenedor, Agente retención IVA
            ("empresa_codigo_postal", ""),
            ("empresa_municipio_codigo", "11001"),  # Bogotá por defecto
            ("empresa_municipio_nombre", "Bogotá D.C."),
            ("empresa_departamento_codigo", "11"),
            ("empresa_departamento_nombre", "Bogotá"),
            ("empresa_pais_codigo", "CO"),
            ("empresa_pais_nombre", "Colombia"),
            ("empresa_nombre_comercial", ""),
            ("empresa_matricula_mercantil", ""),
            
            # Numeración DIAN
            ("dian_resolucion_numero", ""),
            ("dian_resolucion_fecha", ""),
            ("dian_prefijo", "SETT"),
            ("dian_rango_desde", "1"),
            ("dian_rango_hasta", "5000000"),
            ("dian_vigencia_desde", ""),
            ("dian_vigencia_hasta", ""),
            ("dian_clave_tecnica", ""),  # Para calcular CUFE
            
            # Ambiente de facturación
            ("dian_ambiente", "2"),  # 1=Producción, 2=Pruebas
            ("dian_tipo_operacion", "10"),  # 10=Estándar
        ]
        
        for clave, valor in config_empresa:
            cur.execute("""
                INSERT INTO configuracion (clave, valor) 
                VALUES (%s, %s)
                ON CONFLICT (clave) DO NOTHING
            """, (clave, valor))
        
        print("   ✅ Configuración de empresa añadida")
        
        # ==========================================
        # 2. ACTUALIZAR TABLA TERCEROS
        # ==========================================
        print("\n👥 Actualizando tabla terceros...")
        
        cur.execute("""
            ALTER TABLE terceros 
            ADD COLUMN IF NOT EXISTS tipo_identificacion TEXT DEFAULT '13',
            ADD COLUMN IF NOT EXISTS numero_identificacion TEXT,
            ADD COLUMN IF NOT EXISTS digito_verificacion TEXT,
            ADD COLUMN IF NOT EXISTS tipo_persona TEXT DEFAULT '1',
            ADD COLUMN IF NOT EXISTS regimen TEXT DEFAULT '49',
            ADD COLUMN IF NOT EXISTS responsabilidad_fiscal TEXT,
            ADD COLUMN IF NOT EXISTS codigo_postal TEXT,
            ADD COLUMN IF NOT EXISTS municipio_codigo TEXT,
            ADD COLUMN IF NOT EXISTS municipio_nombre TEXT,
            ADD COLUMN IF NOT EXISTS departamento_codigo TEXT,
            ADD COLUMN IF NOT EXISTS departamento_nombre TEXT,
            ADD COLUMN IF NOT EXISTS pais_codigo TEXT DEFAULT 'CO',
            ADD COLUMN IF NOT EXISTS pais_nombre TEXT DEFAULT 'Colombia'
        """)
        
        print("   ✅ Tabla terceros actualizada")
        
        # ==========================================
        # 3. ACTUALIZAR TABLA FACTURAS
        # ==========================================
        print("\n🧾 Actualizando tabla facturas...")
        
        cur.execute("""
            ALTER TABLE facturas 
            ADD COLUMN IF NOT EXISTS prefijo TEXT DEFAULT 'SETT',
            ADD COLUMN IF NOT EXISTS fecha_vencimiento DATE,
            ADD COLUMN IF NOT EXISTS forma_pago TEXT DEFAULT '1',
            ADD COLUMN IF NOT EXISTS medio_pago TEXT DEFAULT '10',
            ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'COP',
            ADD COLUMN IF NOT EXISTS trm REAL DEFAULT 1,
            
            -- Totales desglosados
            ADD COLUMN IF NOT EXISTS subtotal REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_descuentos REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_cargos REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS base_imponible REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_impuestos REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_iva REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_inc REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_retenciones REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_retefuente REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_reteiva REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_reteica REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS redondeo REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS anticipo REAL DEFAULT 0,
            
            -- Facturación electrónica
            ADD COLUMN IF NOT EXISTS cufe TEXT,
            ADD COLUMN IF NOT EXISTS qr_code TEXT,
            ADD COLUMN IF NOT EXISTS uuid TEXT,
            ADD COLUMN IF NOT EXISTS ambiente TEXT DEFAULT '2',
            ADD COLUMN IF NOT EXISTS tipo_operacion TEXT DEFAULT '10',
            ADD COLUMN IF NOT EXISTS estado_dian TEXT DEFAULT 'pendiente',
            ADD COLUMN IF NOT EXISTS fecha_validacion_dian TIMESTAMP,
            ADD COLUMN IF NOT EXISTS xml_dian TEXT,
            ADD COLUMN IF NOT EXISTS pdf_url TEXT,
            
            -- Notas adicionales
            ADD COLUMN IF NOT EXISTS notas TEXT,
            ADD COLUMN IF NOT EXISTS orden_compra TEXT,
            ADD COLUMN IF NOT EXISTS observaciones TEXT
        """)
        
        print("   ✅ Tabla facturas actualizada")
        
        # ==========================================
        # 4. ACTUALIZAR DETALLE FACTURAS
        # ==========================================
        print("\n📝 Actualizando detalle_factura...")
        
        cur.execute("""
            ALTER TABLE detalle_factura 
            ADD COLUMN IF NOT EXISTS codigo_producto TEXT,
            ADD COLUMN IF NOT EXISTS codigo_estandar TEXT,
            ADD COLUMN IF NOT EXISTS codigo_estandar_tipo TEXT DEFAULT '999',
            ADD COLUMN IF NOT EXISTS descripcion TEXT,
            ADD COLUMN IF NOT EXISTS unidad_medida TEXT DEFAULT '94',
            ADD COLUMN IF NOT EXISTS descuento REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS porcentaje_descuento REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS cargo REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS porcentaje_cargo REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS base_imponible REAL DEFAULT 0,
            
            -- Impuestos por línea
            ADD COLUMN IF NOT EXISTS impuesto_tipo TEXT DEFAULT '01',
            ADD COLUMN IF NOT EXISTS impuesto_porcentaje REAL DEFAULT 19,
            ADD COLUMN IF NOT EXISTS impuesto_valor REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_con_impuesto REAL DEFAULT 0,
            
            -- Retenciones por línea
            ADD COLUMN IF NOT EXISTS retencion_tipo TEXT,
            ADD COLUMN IF NOT EXISTS retencion_porcentaje REAL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS retencion_valor REAL DEFAULT 0
        """)
        
        print("   ✅ Tabla detalle_factura actualizada")
        
        # ==========================================
        # 5. ACTUALIZAR TABLA PRODUCTOS
        # ==========================================
        print("\n📦 Actualizando tabla productos...")
        
        cur.execute("""
            ALTER TABLE productos 
            ADD COLUMN IF NOT EXISTS codigo_interno TEXT,
            ADD COLUMN IF NOT EXISTS codigo_barra TEXT,
            ADD COLUMN IF NOT EXISTS codigo_estandar TEXT,
            ADD COLUMN IF NOT EXISTS tipo_codigo_estandar TEXT DEFAULT '999',
            ADD COLUMN IF NOT EXISTS unidad_medida TEXT DEFAULT '94',
            ADD COLUMN IF NOT EXISTS clasificacion TEXT,
            ADD COLUMN IF NOT EXISTS impuesto_tipo TEXT DEFAULT '01',
            ADD COLUMN IF NOT EXISTS impuesto_porcentaje REAL DEFAULT 19,
            ADD COLUMN IF NOT EXISTS precio_sin_iva REAL,
            ADD COLUMN IF NOT EXISTS marca TEXT,
            ADD COLUMN IF NOT EXISTS modelo TEXT
        """)
        
        # Calcular precio sin IVA para productos existentes
        cur.execute("""
            UPDATE productos 
            SET precio_sin_iva = precio / 1.19 
            WHERE precio_sin_iva IS NULL AND precio > 0
        """)
        
        print("   ✅ Tabla productos actualizada")
        
        # ==========================================
        # 6. CREAR TABLA DE IMPUESTOS
        # ==========================================
        print("\n💰 Creando tabla de impuestos...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS impuestos (
                id SERIAL PRIMARY KEY,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL,
                porcentaje REAL NOT NULL,
                descripcion TEXT,
                activo BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Insertar impuestos comunes
        impuestos_comunes = [
            ('01', 'IVA', 'impuesto', 0, 'IVA 0%'),
            ('01', 'IVA', 'impuesto', 5, 'IVA 5%'),
            ('01', 'IVA', 'impuesto', 19, 'IVA 19%'),
            ('04', 'INC', 'impuesto', 8, 'Impuesto Nacional al Consumo 8%'),
            ('05', 'ReteIVA', 'retencion', 15, 'Retención IVA 15%'),
            ('06', 'ReteFuente', 'retencion', 2.5, 'Retención en la Fuente 2.5%'),
            ('07', 'ReteICA', 'retencion', 1, 'Retención ICA 1%'),
        ]
        
        for codigo, nombre, tipo, porcentaje, descripcion in impuestos_comunes:
            cur.execute("""
                INSERT INTO impuestos (codigo, nombre, tipo, porcentaje, descripcion)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (codigo) DO NOTHING
            """, (f"{codigo}_{porcentaje}", nombre, tipo, porcentaje, descripcion))
        
        print("   ✅ Tabla impuestos creada")
        
        # ==========================================
        # 7. CREAR TABLA DE FORMAS DE PAGO
        # ==========================================
        print("\n💳 Creando tabla de formas de pago...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS formas_pago (
                id SERIAL PRIMARY KEY,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                descripcion TEXT
            )
        """)
        
        formas_pago = [
            ('1', 'Contado', 'Pago en efectivo al momento de la venta'),
            ('2', 'Crédito', 'Pago a crédito según términos acordados'),
        ]
        
        for codigo, nombre, descripcion in formas_pago:
            cur.execute("""
                INSERT INTO formas_pago (codigo, nombre, descripcion)
                VALUES (%s, %s, %s)
                ON CONFLICT (codigo) DO NOTHING
            """, (codigo, nombre, descripcion))
        
        print("   ✅ Tabla formas_pago creada")
        
        # ==========================================
        # 8. CREAR TABLA DE MEDIOS DE PAGO
        # ==========================================
        print("\n💵 Creando tabla de medios de pago...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS medios_pago (
                id SERIAL PRIMARY KEY,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                descripcion TEXT
            )
        """)
        
        medios_pago = [
            ('10', 'Efectivo', 'Pago en efectivo'),
            ('48', 'Tarjeta Crédito', 'Pago con tarjeta de crédito'),
            ('49', 'Tarjeta Débito', 'Pago con tarjeta débito'),
            ('42', 'Transferencia', 'Transferencia bancaria'),
            ('1', 'Instrumento no definido', 'Otro medio de pago'),
        ]
        
        for codigo, nombre, descripcion in medios_pago:
            cur.execute("""
                INSERT INTO medios_pago (codigo, nombre, descripcion)
                VALUES (%s, %s, %s)
                ON CONFLICT (codigo) DO NOTHING
            """, (codigo, nombre, descripcion))
        
        print("   ✅ Tabla medios_pago creada")
        
        # ==========================================
        # 9. CREAR ÍNDICES
        # ==========================================
        print("\n🔍 Creando índices...")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_facturas_cufe ON facturas(cufe)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_facturas_estado_dian ON facturas(estado_dian)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_terceros_identificacion ON terceros(numero_identificacion)")
        
        print("   ✅ Índices creados")
        
        conn.commit()
        print("\n✅ ¡Migración completada exitosamente!")
        print("\n📊 Resumen:")
        print("   • Configuración empresa: OK")
        print("   • Terceros: OK")
        print("   • Facturas: OK")
        print("   • Detalle facturas: OK")
        print("   • Productos: OK")
        print("   • Impuestos: OK")
        print("   • Formas de pago: OK")
        print("   • Medios de pago: OK")
        print("   • Índices: OK")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error durante la migración: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL no está definida")
        exit(1)
    
    migrate()
