# Archivo: seed_contabilidad.py
# Ejecutar este script después de init_db.py para poblar cuentas básicas

import sqlite3

def seed_contabilidad():
    conn = sqlite3.connect("pos.db")
    c = conn.cursor()
    
    # Cuentas básicas del PUC para el negocio de pollos
    cuentas_basicas = [
        # ACTIVOS (1000-1999)
        ("1105", "Caja General", "activo"),
        ("1110", "Bancos Comerciales", "activo"),
        ("1305", "Clientes Nacionales", "activo"),
        ("1405", "Inventario de Productos Terminados", "activo"),
        ("1435", "Mercancías no Fabricadas por la Empresa", "activo"),
        ("1540", "Equipo de Oficina", "activo"),
        ("1580", "Muebles y Enseres", "activo"),
        ("1592", "Depreciación Acumulada - Equipo", "activo"),
        
        # PASIVOS (2000-2999)
        ("2205", "Proveedores Nacionales", "pasivo"),
        ("2365", "Retención en la Fuente", "pasivo"),
        ("2404", "IVA por Pagar", "pasivo"),
        ("2505", "Salarios por Pagar", "pasivo"),
        ("2510", "Cesantías Consolidadas", "pasivo"),
        
        # PATRIMONIO (3000-3999)
        ("3105", "Capital Suscrito y Pagado", "patrimonio"),
        ("3605", "Utilidades Acumuladas", "patrimonio"),
        ("3705", "Utilidades del Ejercicio", "patrimonio"),
        
        # INGRESOS (4000-4999)
        ("4135", "Comercio al por Mayor y al Detal", "ingreso"),
        ("4175", "Devoluciones en Ventas", "ingreso"),
        ("4210", "Financieros", "ingreso"),
        
        # GASTOS (5000-5999)
        ("5105", "Gastos de Personal", "gasto"),
        ("5135", "Servicios Públicos", "gasto"),
        ("5140", "Gastos Legales", "gasto"),
        ("5145", "Mantenimiento y Reparaciones", "gasto"),
        ("5195", "Gastos Diversos", "gasto"),
        ("5205", "Gastos de Ventas", "gasto"),
        ("5305", "Gastos Financieros", "gasto"),
        
        # COSTO DE VENTAS (6000-6999)
        ("6135", "Comercio al por Mayor y al Detal", "gasto"),
        ("6205", "Materia Prima", "gasto"),
        ("6210", "Mano de Obra Directa", "gasto"),
    ]
    
    print("Inicializando cuentas del PUC...")
    
    for codigo, nombre, tipo in cuentas_basicas:
        try:
            c.execute("""
                INSERT OR IGNORE INTO puc (codigo, nombre, tipo) 
                VALUES (?, ?, ?)
            """, (codigo, nombre, tipo))
            print(f"✓ Cuenta {codigo} - {nombre}")
        except Exception as e:
            print(f"✗ Error con cuenta {codigo}: {e}")
    
    # Insertar algunos terceros de ejemplo si no existen
    print("\nVerificando terceros de ejemplo...")
    
    terceros_ejemplo = [
        ("Cliente", "General", "", "", "", "Cliente"),
        ("Proveedor", "Principal", "", "", "", "Proveedor"),
        ("Distribuidora", "Avícola Nacional", "3001234567", "info@avicola.com", "Calle 123 #45-67", "Proveedor"),
    ]
    
    for nombres, apellidos, telefono, correo, direccion, tipo in terceros_ejemplo:
        try:
            c.execute("""
                INSERT OR IGNORE INTO terceros (nombres, apellidos, telefono, correo, direccion, tipo)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (nombres, apellidos, telefono, correo, direccion, tipo))
            print(f"✓ Tercero: {nombres} {apellidos} ({tipo})")
        except Exception as e:
            print(f"✗ Error con tercero {nombres}: {e}")
    
    # Insertar algunos productos de ejemplo si no existen
    print("\nVerificando productos de ejemplo...")
    
    productos_ejemplo = [
        ("Pollo Entero", "Pollo entero fresco", 8500, 12000, 50),
        ("Pechuga de Pollo (Kg)", "Pechuga de pollo por kilogramo", 15000, 22000, 30),
        ("Muslos de Pollo (Kg)", "Muslos de pollo por kilogramo", 12000, 18000, 25),
        ("Alitas de Pollo (Kg)", "Alitas de pollo por kilogramo", 10000, 16000, 20),
        ("Pollo Despresado", "Pollo despresado completo", 11000, 16500, 40),
    ]
    
    for nombre, descripcion, costo, precio, stock in productos_ejemplo:
        try:
            c.execute("""
                INSERT OR IGNORE INTO productos (nombre, descripcion, costo, precio, stock)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, descripcion, costo, precio, stock))
            print(f"✓ Producto: {nombre}")
        except Exception as e:
            print(f"✗ Error con producto {nombre}: {e}")
    
    conn.commit()
    conn.close()
    print("\n🎉 Datos iniciales de contabilidad cargados exitosamente!")

if __name__ == "__main__":
    seed_contabilidad()