"""
Módulo de integración para Facturación Electrónica DIAN
Se integra con app.py existente
"""
from datetime import datetime, timedelta
from facturacion_electronica_utils import (
    generar_cufe, generar_hora_colombia, generar_codigo_qr_data,
    validar_nit, calcular_totales_factura, generar_uuid,
    TIPOS_IDENTIFICACION, FORMAS_PAGO, MEDIOS_PAGO, REGIMENES_FISCALES
)


def obtener_configuracion_dian(conn):
    """
    Obtiene la configuración DIAN desde la base de datos
    
    Returns:
        dict: Configuración con todos los parámetros necesarios
    """
    cur = conn.cursor()
    cur.execute("SELECT clave, valor FROM configuracion WHERE clave LIKE 'empresa_%' OR clave LIKE 'dian_%'")
    rows = cur.fetchall()
    
    config = {}
    for row in rows:
        config[row['clave']] = row['valor']
    
    return config


def generar_cufe_factura(conn, factura_id):
    """
    Genera el CUFE para una factura existente
    
    Args:
        conn: Conexión a la base de datos
        factura_id: ID de la factura
        
    Returns:
        tuple: (cufe, qr_data) o (None, None) si hay error
    """
    try:
        cur = conn.cursor()
        
        # Obtener configuración
        config = obtener_configuracion_dian(conn)
        
        # Obtener datos de la factura
        cur.execute("""
            SELECT f.*, t.numero_identificacion as cliente_nit, t.tipo_identificacion as cliente_tipo_doc
            FROM facturas f
            LEFT JOIN terceros t ON f.tercero_id = t.id
            WHERE f.id = %s
        """, (factura_id,))
        factura = cur.fetchone()
        
        if not factura:
            return None, None
        
        # Obtener totales de impuestos
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN impuesto_tipo = '01' THEN impuesto_valor ELSE 0 END), 0) as total_iva,
                COALESCE(SUM(CASE WHEN impuesto_tipo = '04' THEN impuesto_valor ELSE 0 END), 0) as total_inc
            FROM detalle_factura
            WHERE factura_id = %s
        """, (factura_id,))
        impuestos = cur.fetchone()
        
        # Preparar datos para CUFE
        numero_factura = str(factura['numero'])
        fecha_emision = factura['fecha'].strftime('%Y-%m-%d') if hasattr(factura['fecha'], 'strftime') else str(factura['fecha'])
        hora_emision = generar_hora_colombia()
        
        # Valores
        subtotal = float(factura.get('subtotal') or factura.get('total') or 0)
        valor_iva = float(impuestos['total_iva']) if impuestos else 0
        valor_inc = float(impuestos['total_inc']) if impuestos else 0
        total_con_impuestos = float(factura['total'])
        
        # Datos emisor y adquirente
        nit_emisor = config.get('empresa_nit', '').replace('.', '').replace('-', '').split('-')[0]
        tipo_doc_adquirente = factura.get('cliente_tipo_doc') or '13'
        num_doc_adquirente = factura.get('cliente_nit') or '222222222222'
        
        # Clave técnica
        clave_tecnica = config.get('dian_clave_tecnica', '')
        if not clave_tecnica:
            # Generar clave técnica temporal para pruebas
            clave_tecnica = 'clavetemporaltestpruebas'
        
        ambiente = config.get('dian_ambiente', '2')
        
        # Generar CUFE
        cufe = generar_cufe(
            numero_factura=numero_factura,
            fecha_emision=fecha_emision,
            hora_emision=hora_emision,
            valor_total=subtotal,
            cod_imp_1='01',
            val_imp_1=valor_iva,
            cod_imp_2='04',
            val_imp_2=valor_inc,
            cod_imp_3='03',
            val_imp_3=0.0,
            valor_total_con_impuestos=total_con_impuestos,
            nit_emisor=nit_emisor,
            tipo_doc_adquirente=tipo_doc_adquirente,
            num_doc_adquirente=num_doc_adquirente,
            clave_tecnica=clave_tecnica,
            ambiente=ambiente
        )
        
        # Generar datos QR
        prefijo = config.get('dian_prefijo', 'SETT')
        numero_completo = f"{prefijo}{numero_factura}"
        
        qr_data = generar_codigo_qr_data(
            cufe=cufe,
            numero_factura=numero_completo,
            fecha_emision=fecha_emision,
            nit_emisor=nit_emisor,
            nit_adquirente=num_doc_adquirente,
            valor_total=subtotal,
            valor_iva=valor_iva,
            valor_total_con_impuestos=total_con_impuestos
        )
        
        # Actualizar factura con CUFE y QR
        cur.execute("""
            UPDATE facturas 
            SET cufe = %s, qr_code = %s, uuid = %s
            WHERE id = %s
        """, (cufe, qr_data, generar_uuid(), factura_id))
        
        conn.commit()
        
        return cufe, qr_data
        
    except Exception as e:
        print(f"Error generando CUFE: {e}")
        conn.rollback()
        return None, None


def calcular_totales_detalle_factura(lineas):
    """
    Calcula los totales de una factura desde sus líneas
    Prepara la estructura para calcular_totales_factura
    
    Args:
        lineas: Lista de líneas de detalle de factura
        
    Returns:
        dict: Diccionario con todos los totales
    """
    lineas_procesadas = []
    
    for linea in lineas:
        linea_proc = {
            'cantidad': float(linea.get('cantidad', 0)),
            'precio': float(linea.get('precio', 0)),
            'descuento': float(linea.get('descuento', 0)),
            'cargo': float(linea.get('cargo', 0)),
            'impuesto_tipo': linea.get('impuesto_tipo', '01'),
            'impuesto_porcentaje': float(linea.get('impuesto_porcentaje', 19)),
            'retencion_tipo': linea.get('retencion_tipo'),
            'retencion_porcentaje': float(linea.get('retencion_porcentaje', 0)),
        }
        lineas_procesadas.append(linea_proc)
    
    return calcular_totales_factura(lineas_procesadas)


def validar_datos_facturacion_electronica(conn):
    """
    Valida que estén todos los datos necesarios para facturación electrónica
    
    Returns:
        tuple: (es_valido, lista_errores)
    """
    errores = []
    
    try:
        cur = conn.cursor()
        
        # Validar configuración empresa
        config = obtener_configuracion_dian(conn)
        
        campos_requeridos = [
            ('empresa_nit', 'NIT de la empresa'),
            ('empresa_nombre', 'Nombre de la empresa'),
            ('empresa_direccion', 'Dirección de la empresa'),
            ('empresa_municipio_codigo', 'Código del municipio'),
            ('empresa_telefono', 'Teléfono de la empresa'),
            ('dian_resolucion_numero', 'Número de resolución DIAN'),
            ('dian_resolucion_fecha', 'Fecha de resolución DIAN'),
            ('dian_prefijo', 'Prefijo de facturación'),
            ('dian_rango_desde', 'Rango inicial de numeración'),
            ('dian_rango_hasta', 'Rango final de numeración'),
        ]
        
        for campo, nombre in campos_requeridos:
            if not config.get(campo):
                errores.append(f"Falta configurar: {nombre}")
        
        # Validar NIT
        nit = config.get('empresa_nit', '')
        dv = config.get('empresa_digito_verificacion', '')
        if nit:
            nit_limpio = nit.replace('.', '').replace('-', '')
            es_valido, dv_calculado = validar_nit(nit_limpio, dv)
            if not es_valido:
                errores.append(f"NIT inválido o dígito de verificación incorrecto")
        
        return len(errores) == 0, errores
        
    except Exception as e:
        errores.append(f"Error al validar: {str(e)}")
        return False, errores


def actualizar_factura_con_fe(conn, factura_id, data):
    """
    Actualiza una factura con información de facturación electrónica
    
    Args:
        conn: Conexión a BD
        factura_id: ID de la factura
        data: Diccionario con datos adicionales
    """
    try:
        cur = conn.cursor()
        
        # Actualizar campos de FE
        cur.execute("""
            UPDATE facturas SET
                prefijo = COALESCE(%s, prefijo),
                fecha_vencimiento = COALESCE(%s, fecha_vencimiento),
                forma_pago = COALESCE(%s, forma_pago),
                medio_pago = COALESCE(%s, medio_pago),
                notas = COALESCE(%s, notas),
                orden_compra = COALESCE(%s, orden_compra)
            WHERE id = %s
        """, (
            data.get('prefijo'),
            data.get('fecha_vencimiento'),
            data.get('forma_pago', '1'),
            data.get('medio_pago', '10'),
            data.get('notas'),
            data.get('orden_compra'),
            factura_id
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error actualizando factura: {e}")
        conn.rollback()
        return False


def obtener_siguiente_numero_factura(conn):
    """
    Obtiene el siguiente número de factura disponible validando contra el rango DIAN
    
    Returns:
        tuple: (numero, prefijo, es_valido, mensaje)
    """
    try:
        cur = conn.cursor()
        
        # Obtener configuración
        config = obtener_configuracion_dian(conn)
        
        # Obtener último número usado
        prefijo = config.get('dian_prefijo', 'SETT')
        cur.execute("SELECT MAX(numero) as last_num FROM facturas WHERE prefijo = %s", (prefijo,))
        row = cur.fetchone()
        ultimo_numero = row['last_num'] if row and row['last_num'] else 0
        
        siguiente_numero = ultimo_numero + 1
        
        # Validar contra rango DIAN
        rango_desde = int(config.get('dian_rango_desde', 1))
        rango_hasta = int(config.get('dian_rango_hasta', 5000000))
        
        if siguiente_numero < rango_desde:
            return rango_desde, prefijo, True, "OK"
        
        if siguiente_numero > rango_hasta:
            return siguiente_numero, prefijo, False, f"Se agotó el rango autorizado (hasta {rango_hasta})"
        
        return siguiente_numero, prefijo, True, "OK"
        
    except Exception as e:
        return 1, 'SETT', False, f"Error: {str(e)}"


def get_catalogo_dian(tipo):
    """
    Obtiene catálogos según tipo
    
    Args:
        tipo: 'tipos_identificacion', 'formas_pago', 'medios_pago', 'regimenes'
        
    Returns:
        dict: Diccionario con código: descripción
    """
    catalogos = {
        'tipos_identificacion': TIPOS_IDENTIFICACION,
        'formas_pago': FORMAS_PAGO,
        'medios_pago': MEDIOS_PAGO,
        'regimenes': REGIMENES_FISCALES,
    }
    
    return catalogos.get(tipo, {})


# Función auxiliar para formatear moneda
def formatear_moneda(valor):
    """Formatea un valor como moneda colombiana"""
    try:
        return f"${float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return "$0,00"


if __name__ == "__main__":
    print("=== TEST DE INTEGRACIÓN FACTURACIÓN ELECTRÓNICA ===")
    print("\nEste módulo debe ser importado en app.py")
    print("\nFunciones disponibles:")
    print("  - obtener_configuracion_dian(conn)")
    print("  - generar_cufe_factura(conn, factura_id)")
    print("  - calcular_totales_detalle_factura(lineas)")
    print("  - validar_datos_facturacion_electronica(conn)")
    print("  - obtener_siguiente_numero_factura(conn)")
    print("  - get_catalogo_dian(tipo)")
