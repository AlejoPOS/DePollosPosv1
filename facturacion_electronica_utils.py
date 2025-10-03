"""
Utilidades para Facturación Electrónica DIAN
Según Resolución 000165 (01/NOV/2023) - Anexo Técnico v1.9
"""
import hashlib
from datetime import datetime, timedelta
import base64


# ===============================================================
# CÓDIGOS Y CATÁLOGOS SEGÚN ANEXO TÉCNICO
# ===============================================================

TIPOS_IDENTIFICACION = {
    '11': 'Registro civil',
    '12': 'Tarjeta de identidad',
    '13': 'Cédula de ciudadanía',
    '21': 'Tarjeta de extranjería',
    '22': 'Cédula de extranjería',
    '31': 'NIT',
    '41': 'Pasaporte',
    '42': 'Documento de identificación extranjero',
    '50': 'NIT de otro país',
}

TIPOS_ORGANIZACION = {
    '1': 'Persona Jurídica',
    '2': 'Persona Natural',
}

REGIMENES_FISCALES = {
    '48': 'Responsable de IVA',
    '49': 'No responsable de IVA (Régimen Simple)',
}

RESPONSABILIDADES_FISCALES = {
    'O-13': 'Gran contribuyente',
    'O-15': 'Autorretenedor',
    'O-23': 'Agente de retención IVA',
    'O-47': 'Régimen simple de tributación',
    'R-99-PN': 'No aplica - Otros',
}

TIPOS_IMPUESTOS = {
    '01': 'IVA',
    '04': 'INC (Impuesto Nacional al Consumo)',
    '05': 'ReteIVA',
    '06': 'ReteFuente',
    '07': 'ReteICA',
}

FORMAS_PAGO = {
    '1': 'Contado',
    '2': 'Crédito',
}

MEDIOS_PAGO = {
    '1': 'Instrumento no definido',
    '10': 'Efectivo',
    '42': 'Consignación bancaria',
    '47': 'Transferencia débito bancaria',
    '48': 'Tarjeta crédito',
    '49': 'Tarjeta débito',
}

UNIDADES_MEDIDA = {
    '94': 'Unidad',
    'KGM': 'Kilogramo',
    'GRM': 'Gramo',
    'MTR': 'Metro',
    'LTR': 'Litro',
    'HUR': 'Hora',
    'DAY': 'Día',
}


# ===============================================================
# GENERACIÓN DE CUFE
# ===============================================================

def generar_cufe(
    numero_factura,
    fecha_emision,
    hora_emision,
    valor_total,
    cod_imp_1='01',
    val_imp_1=0.0,
    cod_imp_2='04',
    val_imp_2=0.0,
    cod_imp_3='03',
    val_imp_3=0.0,
    valor_total_con_impuestos=None,
    nit_emisor='',
    tipo_doc_adquirente='',
    num_doc_adquirente='',
    clave_tecnica='',
    ambiente='2'
):
    """
    Genera el CUFE según el anexo técnico DIAN versión 1.9
    
    CUFE = SHA-384(
        NumFac +
        FecFac +
        HorFac +
        ValFac +
        CodImp1 + ValImp1 +
        CodImp2 + ValImp2 +
        CodImp3 + ValImp3 +
        ValTot +
        NitOFE +
        TipAdq + 
        NumAdq +
        ClTec +
        Ambiente
    )
    
    Args:
        numero_factura: Número de la factura (sin prefijo)
        fecha_emision: Fecha en formato YYYY-MM-DD
        hora_emision: Hora en formato HH:MM:SS-05:00
        valor_total: Valor antes de impuestos
        cod_imp_1: Código impuesto 1 (por defecto '01' = IVA)
        val_imp_1: Valor impuesto 1
        cod_imp_2: Código impuesto 2 (por defecto '04' = INC)
        val_imp_2: Valor impuesto 2
        cod_imp_3: Código impuesto 3 (por defecto '03' = ICA)
        val_imp_3: Valor impuesto 3
        valor_total_con_impuestos: Valor total incluyendo impuestos
        nit_emisor: NIT del emisor (sin dígito de verificación)
        tipo_doc_adquirente: Tipo documento adquirente
        num_doc_adquirente: Número documento adquirente
        clave_tecnica: Clave técnica asignada por DIAN
        ambiente: '1' producción, '2' pruebas
        
    Returns:
        str: CUFE de 96 caracteres hexadecimales
    """
    
    if valor_total_con_impuestos is None:
        valor_total_con_impuestos = valor_total + val_imp_1 + val_imp_2 + val_imp_3
    
    # Formatear valores con 2 decimales
    valor_total_fmt = f"{float(valor_total):.2f}"
    val_imp_1_fmt = f"{float(val_imp_1):.2f}"
    val_imp_2_fmt = f"{float(val_imp_2):.2f}"
    val_imp_3_fmt = f"{float(val_imp_3):.2f}"
    valor_total_con_imp_fmt = f"{float(valor_total_con_impuestos):.2f}"
    
    # Construir cadena para hash
    cadena_cufe = (
        f"{numero_factura}"
        f"{fecha_emision}"
        f"{hora_emision}"
        f"{valor_total_fmt}"
        f"{cod_imp_1}{val_imp_1_fmt}"
        f"{cod_imp_2}{val_imp_2_fmt}"
        f"{cod_imp_3}{val_imp_3_fmt}"
        f"{valor_total_con_imp_fmt}"
        f"{nit_emisor}"
        f"{tipo_doc_adquirente}"
        f"{num_doc_adquirente}"
        f"{clave_tecnica}"
        f"{ambiente}"
    )
    
    # Calcular SHA-384
    cufe = hashlib.sha384(cadena_cufe.encode('utf-8')).hexdigest()
    
    return cufe.upper()


def generar_hora_colombia():
    """
    Genera la hora actual en formato requerido para CUFE
    HH:MM:SS-05:00 (hora de Colombia)
    """
    return datetime.now().strftime("%H:%M:%S-05:00")


# ===============================================================
# GENERACIÓN DE CÓDIGO QR
# ===============================================================

def generar_codigo_qr_data(
    cufe,
    numero_factura,
    fecha_emision,
    nit_emisor,
    nit_adquirente,
    valor_total,
    valor_iva,
    valor_total_con_impuestos,
    url_validacion=None
):
    """
    Genera los datos para el código QR según especificaciones DIAN
    
    El QR debe contener mínimo:
    - CUFE
    - Número de factura  
    - Fecha de emisión
    - NIT emisor
    - NIT adquirente
    - Valor total
    - Valor IVA
    - Total con impuestos
    - URL de validación
    
    Args:
        cufe: CUFE de la factura
        numero_factura: Número completo con prefijo
        fecha_emision: Fecha YYYY-MM-DD
        nit_emisor: NIT del emisor
        nit_adquirente: NIT del adquirente
        valor_total: Subtotal antes de impuestos
        valor_iva: Valor del IVA
        valor_total_con_impuestos: Total con impuestos
        url_validacion: URL para validar en portal DIAN
        
    Returns:
        str: Cadena de datos para generar QR
    """
    
    if url_validacion is None:
        # URL por defecto del portal DIAN para validación
        url_validacion = f"https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={cufe}"
    
    # Formato según anexo técnico
    qr_data = (
        f"NumFac: {numero_factura}\n"
        f"FecFac: {fecha_emision}\n"
        f"NitFac: {nit_emisor}\n"
        f"DocAdq: {nit_adquirente}\n"
        f"ValFac: {valor_total:.2f}\n"
        f"ValIva: {valor_iva:.2f}\n"
        f"ValOtroIm: 0.00\n"
        f"ValTot: {valor_total_con_impuestos:.2f}\n"
        f"CUFE: {cufe}\n"
        f"URL: {url_validacion}"
    )
    
    return qr_data


# ===============================================================
# VALIDACIONES BÁSICAS
# ===============================================================

def validar_nit(nit, digito_verificacion=None):
    """
    Valida un NIT colombiano y calcula el dígito de verificación
    
    Args:
        nit: Número de identificación tributaria
        digito_verificacion: Dígito de verificación (opcional)
        
    Returns:
        tuple: (es_valido, digito_calculado)
    """
    try:
        nit_str = str(nit).replace('.', '').replace('-', '').replace(' ', '')
        
        # Pesos para cálculo del DV
        pesos = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]
        
        suma = 0
        nit_reverso = nit_str[::-1]
        
        for i, digito in enumerate(nit_reverso):
            if i < len(pesos):
                suma += int(digito) * pesos[i]
        
        residuo = suma % 11
        
        if residuo == 0 or residuo == 1:
            dv = residuo
        else:
            dv = 11 - residuo
        
        if digito_verificacion is not None:
            es_valido = str(dv) == str(digito_verificacion)
            return es_valido, str(dv)
        
        return True, str(dv)
        
    except Exception:
        return False, None


def validar_fecha_vencimiento(fecha_emision, fecha_vencimiento, forma_pago):
    """
    Valida que la fecha de vencimiento sea coherente con la forma de pago
    
    Args:
        fecha_emision: Fecha de emisión
        fecha_vencimiento: Fecha de vencimiento
        forma_pago: '1' = Contado, '2' = Crédito
        
    Returns:
        tuple: (es_valido, mensaje)
    """
    try:
        if isinstance(fecha_emision, str):
            fecha_emision = datetime.strptime(fecha_emision, "%Y-%m-%d")
        if isinstance(fecha_vencimiento, str):
            fecha_vencimiento = datetime.strptime(fecha_vencimiento, "%Y-%m-%d")
        
        # Para contado, fecha vencimiento debe ser igual a fecha emisión
        if forma_pago == '1':
            if fecha_vencimiento != fecha_emision:
                return False, "Para pago de contado, la fecha de vencimiento debe ser igual a la de emisión"
        
        # Para crédito, fecha vencimiento debe ser posterior
        if forma_pago == '2':
            if fecha_vencimiento <= fecha_emision:
                return False, "Para pago a crédito, la fecha de vencimiento debe ser posterior a la de emisión"
        
        return True, "OK"
        
    except Exception as e:
        return False, f"Error validando fechas: {str(e)}"


def calcular_totales_factura(lineas, redondeo=True):
    """
    Calcula todos los totales de una factura según normativa DIAN
    
    Args:
        lineas: Lista de diccionarios con líneas de factura
        redondeo: Si True, aplica redondeo según norma
        
    Returns:
        dict: Diccionario con todos los totales calculados
    """
    totales = {
        'subtotal': 0.0,
        'total_descuentos': 0.0,
        'total_cargos': 0.0,
        'base_imponible': 0.0,
        'total_iva': 0.0,
        'total_inc': 0.0,
        'total_impuestos': 0.0,
        'total_retenciones': 0.0,
        'total_retefuente': 0.0,
        'total_reteiva': 0.0,
        'total_reteica': 0.0,
        'redondeo': 0.0,
        'total': 0.0,
    }
    
    for linea in lineas:
        cantidad = float(linea.get('cantidad', 0))
        precio = float(linea.get('precio', 0))
        descuento = float(linea.get('descuento', 0))
        cargo = float(linea.get('cargo', 0))
        
        # Subtotal línea
        subtotal_linea = cantidad * precio
        totales['subtotal'] += subtotal_linea
        
        # Descuentos
        totales['total_descuentos'] += descuento
        
        # Cargos
        totales['total_cargos'] += cargo
        
        # Base imponible = subtotal - descuentos + cargos
        base_linea = subtotal_linea - descuento + cargo
        totales['base_imponible'] += base_linea
        
        # Impuestos
        impuesto_porcentaje = float(linea.get('impuesto_porcentaje', 0))
        if impuesto_porcentaje > 0:
            impuesto_valor = base_linea * (impuesto_porcentaje / 100)
            
            impuesto_tipo = linea.get('impuesto_tipo', '01')
            if impuesto_tipo == '01':  # IVA
                totales['total_iva'] += impuesto_valor
            elif impuesto_tipo == '04':  # INC
                totales['total_inc'] += impuesto_valor
            
            totales['total_impuestos'] += impuesto_valor
        
        # Retenciones
        retencion_porcentaje = float(linea.get('retencion_porcentaje', 0))
        if retencion_porcentaje > 0:
            retencion_valor = base_linea * (retencion_porcentaje / 100)
            
            retencion_tipo = linea.get('retencion_tipo', '06')
            if retencion_tipo == '06':  # ReteFuente
                totales['total_retefuente'] += retencion_valor
            elif retencion_tipo == '05':  # ReteIVA
                totales['total_reteiva'] += retencion_valor
            elif retencion_tipo == '07':  # ReteICA
                totales['total_reteica'] += retencion_valor
            
            totales['total_retenciones'] += retencion_valor
    
    # Total = base + impuestos - retenciones
    total_antes_redondeo = (
        totales['base_imponible'] + 
        totales['total_impuestos'] - 
        totales['total_retenciones']
    )
    
    # Redondeo según norma (múltiplo de 50 o 100)
    if redondeo:
        total_redondeado = round(total_antes_redondeo / 50) * 50
        totales['redondeo'] = total_redondeado - total_antes_redondeo
        totales['total'] = total_redondeado
    else:
        totales['total'] = round(total_antes_redondeo, 2)
    
    # Redondear todos los valores a 2 decimales
    for key in totales:
        totales[key] = round(totales[key], 2)
    
    return totales


def generar_uuid():
    """
    Genera un UUID único para la factura
    """
    import uuid
    return str(uuid.uuid4())


def obtener_consecutivo_factura(ultimo_numero, prefijo='SETT'):
    """
    Genera el siguiente número de factura
    
    Args:
        ultimo_numero: Último número usado
        prefijo: Prefijo de la factura
        
    Returns:
        tuple: (numero_completo, numero_sin_prefijo)
    """
    siguiente = int(ultimo_numero) + 1
    numero_completo = f"{prefijo}{siguiente}"
    return numero_completo, str(siguiente)


# ===============================================================
# UTILIDADES DE FORMATO
# ===============================================================

def formatear_nit(nit, digito_verificacion):
    """
    Formatea un NIT con separadores y DV
    """
    nit_str = str(nit).replace('.', '').replace('-', '')
    
    # Añadir separadores de miles
    nit_formateado = f"{int(nit_str):,}".replace(',', '.')
    
    return f"{nit_formateado}-{digito_verificacion}"


def parsear_nit(nit_formateado):
    """
    Extrae NIT y DV de un NIT formateado
    
    Returns:
        tuple: (nit, digito_verificacion)
    """
    partes = nit_formateado.replace('.', '').split('-')
    if len(partes) == 2:
        return partes[0], partes[1]
    return partes[0], None


if __name__ == "__main__":
    # Ejemplo de uso
    print("=== TEST DE UTILIDADES FACTURACIÓN ELECTRÓNICA ===\n")
    
    # Test 1: Validar NIT
    print("1. Validación de NIT:")
    nit = "900123456"
    es_valido, dv = validar_nit(nit)
    print(f"   NIT: {nit}")
    print(f"   DV calculado: {dv}")
    print(f"   Válido: {es_valido}\n")
    
    # Test 2: Generar CUFE
    print("2. Generación de CUFE:")
    cufe = generar_cufe(
        numero_factura="123",
        fecha_emision="2024-01-15",
        hora_emision="10:30:00-05:00",
        valor_total=100000.00,
        val_imp_1=19000.00,
        valor_total_con_impuestos=119000.00,
        nit_emisor="900123456",
        tipo_doc_adquirente="13",
        num_doc_adquirente="1234567890",
        clave_tecnica="testclave123",
        ambiente="2"
    )
    print(f"   CUFE: {cufe}\n")
    
    # Test 3: Datos QR
    print("3. Datos para código QR:")
    qr_data = generar_codigo_qr_data(
        cufe=cufe,
        numero_factura="SETT123",
        fecha_emision="2024-01-15",
        nit_emisor="900123456",
        nit_adquirente="1234567890",
        valor_total=100000.00,
        valor_iva=19000.00,
        valor_total_con_impuestos=119000.00
    )
    print(f"{qr_data}\n")
    
    # Test 4: Calcular totales
    print("4. Cálculo de totales:")
    lineas = [
        {'cantidad': 2, 'precio': 50000, 'descuento': 0, 'cargo': 0, 
         'impuesto_tipo': '01', 'impuesto_porcentaje': 19},
        {'cantidad': 1, 'precio': 30000, 'descuento': 3000, 'cargo': 0,
         'impuesto_tipo': '01', 'impuesto_porcentaje': 19},
    ]
    totales = calcular_totales_factura(lineas)
    for key, value in totales.items():
        print(f"   {key}: ${value:,.2f}")
