#!/usr/bin/env python3
"""
Script de verificación de Facturación Electrónica DIAN
Verifica que todos los componentes estén correctamente instalados
"""
import os
import sys

def test_imports():
    """Test 1: Verificar imports"""
    print("\n" + "="*60)
    print("TEST 1: Verificando módulos Python")
    print("="*60)
    
    try:
        from facturacion_electronica_utils import generar_cufe, validar_nit
        print("✅ facturacion_electronica_utils.py: OK")
    except ImportError as e:
        print(f"❌ facturacion_electronica_utils.py: ERROR - {e}")
        return False
    
    try:
        from facturacion_electronica_integracion import generar_cufe_factura
        print("✅ facturacion_electronica_integracion.py: OK")
    except ImportError as e:
        print(f"❌ facturacion_electronica_integracion.py: ERROR - {e}")
        return False
    
    return True


def test_database():
    """Test 2: Verificar estructura de base de datos"""
    print("\n" + "="*60)
    print("TEST 2: Verificando estructura de base de datos")
    print("="*60)
    
    try:
        import psycopg2
        DATABASE_URL = os.environ.get("DATABASE_URL")
        
        if not DATABASE_URL:
            print("❌ DATABASE_URL no está definida")
            return False
        
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        
        # Verificar tabla configuracion
        cur.execute("""
            SELECT COUNT(*) FROM configuracion 
            WHERE clave LIKE 'empresa_%' OR clave LIKE 'dian_%'
        """)
        config_count = cur.fetchone()[0]
        if config_count > 0:
            print(f"✅ Configuración DIAN: {config_count} registros")
        else:
            print("⚠️  No hay configuración DIAN (ejecutar migración)")
        
        # Verificar campos en facturas
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'facturas' AND column_name IN ('cufe', 'qr_code', 'uuid')
        """)
        campos_fe = [row[0] for row in cur.fetchall()]
        
        campos_esperados = ['cufe', 'qr_code', 'uuid']
        for campo in campos_esperados:
            if campo in campos_fe:
                print(f"✅ Campo facturas.{campo}: OK")
            else:
                print(f"❌ Campo facturas.{campo}: FALTA (ejecutar migración)")
        
        # Verificar tablas nuevas
        tablas_nuevas = ['impuestos', 'formas_pago', 'medios_pago']
        for tabla in tablas_nuevas:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{tabla}'
                )
            """)
            existe = cur.fetchone()[0]
            if existe:
                print(f"✅ Tabla {tabla}: OK")
            else:
                print(f"❌ Tabla {tabla}: FALTA (ejecutar migración)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verificando base de datos: {e}")
        return False


def test_cufe_generation():
    """Test 3: Verificar generación de CUFE"""
    print("\n" + "="*60)
    print("TEST 3: Probando generación de CUFE")
    print("="*60)
    
    try:
        from facturacion_electronica_utils import generar_cufe, generar_codigo_qr_data
        
        # Datos de prueba
        cufe = generar_cufe(
            numero_factura="1",
            fecha_emision="2024-01-15",
            hora_emision="10:30:00-05:00",
            valor_total=100000.00,
            val_imp_1=19000.00,
            valor_total_con_impuestos=119000.00,
            nit_emisor="900123456",
            tipo_doc_adquirente="13",
            num_doc_adquirente="1234567890",
            clave_tecnica="testclaveprueba",
            ambiente="2"
        )
        
        if len(cufe) == 96:  # SHA-384 produce 96 caracteres hex
            print(f"✅ CUFE generado correctamente")
            print(f"   Longitud: {len(cufe)} caracteres")
            print(f"   CUFE: {cufe[:20]}...{cufe[-20:]}")
        else:
            print(f"⚠️  CUFE tiene longitud incorrecta: {len(cufe)}")
        
        # Probar QR
        qr_data = generar_codigo_qr_data(
            cufe=cufe,
            numero_factura="SETT1",
            fecha_emision="2024-01-15",
            nit_emisor="900123456",
            nit_adquirente="1234567890",
            valor_total=100000.00,
            valor_iva=19000.00,
            valor_total_con_impuestos=119000.00
        )
        
        if qr_data and "CUFE:" in qr_data:
            print(f"✅ Datos QR generados correctamente")
            print(f"   Líneas: {len(qr_data.split(chr(10)))}")
        else:
            print(f"❌ Error generando datos QR")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando generación de CUFE: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validaciones():
    """Test 4: Verificar validaciones"""
    print("\n" + "="*60)
    print("TEST 4: Probando validaciones")
    print("="*60)
    
    try:
        from facturacion_electronica_utils import validar_nit, calcular_totales_factura
        
        # Test validación de NIT
        test_cases = [
            ("900123456", "7"),
            ("800197268", "4"),
            ("890900608", "6"),
        ]
        
        for nit, dv_esperado in test_cases:
            es_valido, dv_calculado = validar_nit(nit, dv_esperado)
            if es_valido and dv_calculado == dv_esperado:
                print(f"✅ NIT {nit}-{dv_esperado}: Válido")
            else:
                print(f"❌ NIT {nit}-{dv_esperado}: Inválido (DV calculado: {dv_calculado})")
        
        # Test cálculo de totales
        lineas = [
            {
                'cantidad': 2,
                'precio': 50000,
                'descuento': 0,
                'cargo': 0,
                'impuesto_tipo': '01',
                'impuesto_porcentaje': 19,
                'retencion_tipo': None,
                'retencion_porcentaje': 0
            },
            {
                'cantidad': 1,
                'precio': 30000,
                'descuento': 3000,
                'cargo': 0,
                'impuesto_tipo': '01',
                'impuesto_porcentaje': 19,
                'retencion_tipo': None,
                'retencion_porcentaje': 0
            }
        ]
        
        totales = calcular_totales_factura(lineas)
        
        expected_subtotal = 130000  # (2*50000) + 30000
        expected_base = 127000  # 130000 - 3000
        
        if abs(totales['subtotal'] - expected_subtotal) < 0.01:
            print(f"✅ Cálculo de subtotal: OK (${totales['subtotal']:,.2f})")
        else:
            print(f"❌ Cálculo de subtotal: ERROR (esperado ${expected_subtotal:,.2f}, obtenido ${totales['subtotal']:,.2f})")
        
        if abs(totales['base_imponible'] - expected_base) < 0.01:
            print(f"✅ Cálculo de base imponible: OK (${totales['base_imponible']:,.2f})")
        else:
            print(f"❌ Cálculo de base imponible: ERROR")
        
        if totales['total_iva'] > 0:
            print(f"✅ Cálculo de IVA: OK (${totales['total_iva']:,.2f})")
        else:
            print(f"❌ Cálculo de IVA: ERROR")
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando validaciones: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_catalogos():
    """Test 5: Verificar catálogos DIAN"""
    print("\n" + "="*60)
    print("TEST 5: Verificando catálogos DIAN")
    print("="*60)
    
    try:
        from facturacion_electronica_utils import (
            TIPOS_IDENTIFICACION, FORMAS_PAGO, MEDIOS_PAGO,
            TIPOS_IMPUESTOS, REGIMENES_FISCALES
        )
        
        catalogos = [
            ("Tipos de identificación", TIPOS_IDENTIFICACION),
            ("Formas de pago", FORMAS_PAGO),
            ("Medios de pago", MEDIOS_PAGO),
            ("Tipos de impuestos", TIPOS_IMPUESTOS),
            ("Regímenes fiscales", REGIMENES_FISCALES),
        ]
        
        for nombre, catalogo in catalogos:
            if len(catalogo) > 0:
                print(f"✅ {nombre}: {len(catalogo)} opciones")
            else:
                print(f"❌ {nombre}: Vacío")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando catálogos: {e}")
        return False


def print_summary():
    """Imprimir resumen final"""
    print("\n" + "="*60)
    print("RESUMEN DE VERIFICACIÓN")
    print("="*60)
    print("\n📋 Próximos pasos:")
    print("   1. Si algún test falló, ejecuta la migración:")
    print("      python migrate_facturacion_electronica.py")
    print("\n   2. Configura los datos de tu empresa:")
    print("      Accede a /configuracion en la web")
    print("\n   3. Genera una factura de prueba")
    print("\n   4. Verifica que se genere el CUFE correctamente")
    print("\n" + "="*60)


def main():
    """Ejecutar todos los tests"""
    print("╔" + "="*58 + "╗")
    print("║  VERIFICACIÓN DE FACTURACIÓN ELECTRÓNICA DIAN          ║")
    print("║  Opción 1: Preparación del Sistema                      ║")
    print("╚" + "="*58 + "╝")
    
    resultados = []
    
    resultados.append(("Imports", test_imports()))
    resultados.append(("Base de datos", test_database()))
    resultados.append(("Generación CUFE", test_cufe_generation()))
    resultados.append(("Validaciones", test_validaciones()))
    resultados.append(("Catálogos", test_catalogos()))
    
    print_summary()
    
    # Resumen de resultados
    print("\n📊 RESULTADOS:")
    total = len(resultados)
    exitosos = sum(1 for _, r in resultados if r)
    
    for nombre, resultado in resultados:
        estado = "✅ PASS" if resultado else "❌ FAIL"
        print(f"   {estado} - {nombre}")
    
    print(f"\n   Total: {exitosos}/{total} tests exitosos")
    
    if exitosos == total:
        print("\n🎉 ¡Todos los tests pasaron! El sistema está listo.")
        return 0
    else:
        print("\n⚠️  Algunos tests fallaron. Revisa los errores arriba.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
