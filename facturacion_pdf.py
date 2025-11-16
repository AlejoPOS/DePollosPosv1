"""
Módulo para generación de PDFs de facturas electrónicas DIAN
Incluye código QR, logo, y formato profesional
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import qrcode
from io import BytesIO
from datetime import datetime
import os

# ======================================================================
# CONFIGURACIÓN
# ======================================================================

def generar_qr_imagen(texto_qr, tamaño=(2*inch, 2*inch)):
    """
    Genera una imagen de código QR desde texto
    
    Args:
        texto_qr: Texto a codificar en el QR
        tamaño: Tupla (ancho, alto) en pulgadas
    
    Returns:
        BytesIO: Objeto de imagen QR
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(texto_qr)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a BytesIO
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    return img_buffer


def formatear_numero(numero, decimales=2):
    """Formatea número con separadores de miles y decimales"""
    return f"${numero:,.{decimales}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def formatear_nit(nit, dv):
    """Formatea NIT con dígito de verificación"""
    if dv:
        return f"{nit}-{dv}"
    return nit


# ======================================================================
# GENERACIÓN DE PDF
# ======================================================================

def generar_pdf_factura(factura_data, output_path=None):
    """
    Genera PDF de factura electrónica con código QR
    
    Args:
        factura_data: Diccionario con datos de la factura:
            - id: ID de factura
            - numero: Número de factura
            - prefijo: Prefijo DIAN
            - fecha: Fecha de factura
            - cufe: CUFE de la factura
            - qr_code: Datos del código QR
            - empresa: Dict con datos de empresa
            - cliente: Dict con datos del cliente
            - items: Lista de items de la factura
            - totales: Dict con subtotal, iva, total
        output_path: Ruta donde guardar el PDF (opcional)
    
    Returns:
        str: Ruta del archivo generado o BytesIO si no se especifica ruta
    """
    
    # Si no se especifica ruta, crear en memoria
    if output_path is None:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
    else:
        doc = SimpleDocTemplate(output_path, pagesize=letter)
    
    # Lista de elementos del PDF
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    titulo_style = ParagraphStyle(
        'TituloFactura',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2C3E50'),
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    subtitulo_style = ParagraphStyle(
        'Subtitulo',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#7F8C8D'),
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    seccion_titulo_style = ParagraphStyle(
        'SeccionTitulo',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=6,
        spaceBefore=12
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 9
    
    # ======================================================================
    # ENCABEZADO
    # ======================================================================
    
    # Logo (si existe)
    logo_path = factura_data.get('empresa', {}).get('logo_path')
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=1.5*inch, height=1.5*inch)
            elements.append(logo)
            elements.append(Spacer(1, 0.2*inch))
        except:
            pass  # Si hay error cargando logo, continuar sin él
    
    # Nombre de la empresa
    empresa = factura_data.get('empresa', {})
    elements.append(Paragraph(f"<b>{empresa.get('nombre', 'EMPRESA')}</b>", titulo_style))
    
    # NIT
    nit = formatear_nit(
        empresa.get('nit', ''),
        empresa.get('digito_verificacion', '')
    )
    elements.append(Paragraph(f"NIT: {nit}", subtitulo_style))
    
    # Régimen
    regimen = empresa.get('regimen_nombre', 'Régimen Común')
    elements.append(Paragraph(regimen, subtitulo_style))
    
    # Dirección y contacto
    elements.append(Paragraph(
        f"{empresa.get('direccion', '')} - {empresa.get('municipio', '')}",
        subtitulo_style
    ))
    elements.append(Paragraph(
        f"Tel: {empresa.get('telefono', '')} - Email: {empresa.get('email', '')}",
        subtitulo_style
    ))
    
    elements.append(Spacer(1, 0.3*inch))
    
    # ======================================================================
    # INFORMACIÓN DE FACTURA
    # ======================================================================
    
    # Tipo de documento
    elements.append(Paragraph(
        "<b>FACTURA ELECTRÓNICA DE VENTA</b>",
        titulo_style
    ))
    
    # Número de factura
    numero_factura = f"{factura_data.get('prefijo', '')}{factura_data.get('numero', '')}"
    elements.append(Paragraph(f"No. {numero_factura}", subtitulo_style))
    
    elements.append(Spacer(1, 0.2*inch))
    
    # Tabla con información de factura y cliente
    info_data = [
        ['INFORMACIÓN DE FACTURA', 'INFORMACIÓN DEL CLIENTE'],
    ]
    
    # Columna izquierda (info factura)
    fecha = factura_data.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    resolucion = empresa.get('resolucion_numero', 'N/A')
    fecha_resolucion = empresa.get('resolucion_fecha', 'N/A')
    rango = f"{empresa.get('rango_desde', '0')} - {empresa.get('rango_hasta', '0')}"
    
    info_factura = f"""
    <b>Fecha:</b> {fecha}<br/>
    <b>Resolución DIAN:</b> {resolucion}<br/>
    <b>Fecha Resolución:</b> {fecha_resolucion}<br/>
    <b>Rango Autorizado:</b> {rango}<br/>
    <b>Forma de Pago:</b> {factura_data.get('forma_pago_nombre', 'Contado')}<br/>
    <b>Medio de Pago:</b> {factura_data.get('medio_pago_nombre', 'Efectivo')}
    """
    
    # Columna derecha (info cliente)
    cliente = factura_data.get('cliente', {})
    nit_cliente = formatear_nit(
        cliente.get('numero_identificacion', ''),
        cliente.get('digito_verificacion', '')
    )
    
    info_cliente = f"""
    <b>Cliente:</b> {cliente.get('nombre', 'N/A')}<br/>
    <b>{cliente.get('tipo_identificacion_nombre', 'NIT')}:</b> {nit_cliente}<br/>
    <b>Dirección:</b> {cliente.get('direccion', 'N/A')}<br/>
    <b>Teléfono:</b> {cliente.get('telefono', 'N/A')}<br/>
    <b>Email:</b> {cliente.get('email', 'N/A')}<br/>
    <b>Régimen:</b> {cliente.get('regimen_nombre', 'N/A')}
    """
    
    info_data.append([
        Paragraph(info_factura, normal_style),
        Paragraph(info_cliente, normal_style)
    ])
    
    info_table = Table(info_data, colWidths=[3.5*inch, 3.5*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BOX', (0, 0), (-1, -1), 2, colors.black),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # ======================================================================
    # DETALLE DE PRODUCTOS/SERVICIOS
    # ======================================================================
    
    elements.append(Paragraph("<b>DETALLE DE PRODUCTOS/SERVICIOS</b>", seccion_titulo_style))
    
    # Encabezados
    items_data = [[
        'Ítem',
        'Descripción',
        'Cant.',
        'V. Unit.',
        'IVA',
        'V. Total'
    ]]
    
    # Items
    items = factura_data.get('items', [])
    for idx, item in enumerate(items, 1):
        items_data.append([
            str(idx),
            item.get('nombre', ''),
            str(item.get('cantidad', 0)),
            formatear_numero(item.get('precio_unitario', 0)),
            f"{item.get('iva_porcentaje', 0)}%",
            formatear_numero(item.get('total', 0))
        ])
    
    items_table = Table(items_data, colWidths=[0.5*inch, 3*inch, 0.7*inch, 1*inch, 0.7*inch, 1.3*inch])
    items_table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Contenido
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Ítem
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Descripción
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Números
        
        # Bordes
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 2, colors.black),
        
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        
        # Alternar colores de filas
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # ======================================================================
    # TOTALES
    # ======================================================================
    
    totales = factura_data.get('totales', {})
    
    totales_data = [
        ['Subtotal:', formatear_numero(totales.get('subtotal', 0))],
        ['IVA:', formatear_numero(totales.get('iva', 0))],
        ['', ''],  # Separador
        ['TOTAL:', formatear_numero(totales.get('total', 0))]
    ]
    
    totales_table = Table(totales_data, colWidths=[5.2*inch, 1.8*inch])
    totales_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 2), 10),
        ('FONTSIZE', (0, 3), (-1, 3), 12),
        ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#2C3E50')),
        ('LINEABOVE', (0, 3), (-1, 3), 2, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    elements.append(totales_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # ======================================================================
    # CÓDIGO QR Y CUFE
    # ======================================================================
    
    cufe = factura_data.get('cufe', '')
    qr_data = factura_data.get('qr_code', '')
    
    if cufe and qr_data:
        elements.append(Paragraph("<b>INFORMACIÓN DE FACTURA ELECTRÓNICA</b>", seccion_titulo_style))
        
        # Crear tabla con QR y CUFE
        qr_buffer = generar_qr_imagen(qr_data, tamaño=(1.5*inch, 1.5*inch))
        qr_image = Image(qr_buffer, width=1.5*inch, height=1.5*inch)
        
        # Texto del CUFE (dividido en líneas)
        cufe_texto = f"""
        <b>CUFE (Código Único de Factura Electrónica):</b><br/>
        <font size=7>{cufe[:48]}<br/>
        {cufe[48:] if len(cufe) > 48 else ''}</font><br/>
        <br/>
        <b>Para validar esta factura electrónica, escanee el código QR<br/>
        o consulte en:</b><br/>
        https://catalogo-vpfe.dian.gov.co/
        """
        
        qr_cufe_data = [[
            qr_image,
            Paragraph(cufe_texto, normal_style)
        ]]
        
        qr_cufe_table = Table(qr_cufe_data, colWidths=[2*inch, 5*inch])
        qr_cufe_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(qr_cufe_table)
    
    elements.append(Spacer(1, 0.2*inch))
    
    # ======================================================================
    # PIE DE PÁGINA
    # ======================================================================
    
    pie_texto = """
    <font size=7>
    <b>NOTA LEGAL:</b> Esta factura electrónica fue generada conforme a la Resolución DIAN 000165 de 2023.
    La ausencia de firma autógrafa no afecta la validez del documento.<br/>
    <br/>
    <b>Generado por:</b> A&S System POS v2.0 con Facturación Electrónica DIAN
    </font>
    """
    
    elements.append(Paragraph(pie_texto, subtitulo_style))
    
    # ======================================================================
    # CONSTRUIR PDF
    # ======================================================================
    
    doc.build(elements)
    
    if output_path is None:
        buffer.seek(0)
        return buffer
    else:
        return output_path


# ======================================================================
# FUNCIÓN PARA OBTENER DATOS DE FACTURA DESDE BD
# ======================================================================

def obtener_datos_factura_para_pdf(conn, factura_id):
    """
    Obtiene todos los datos necesarios de la BD para generar el PDF
    
    Args:
        conn: Conexión a la base de datos
        factura_id: ID de la factura
    
    Returns:
        dict: Diccionario con todos los datos formateados
    """
    from psycopg2.extras import RealDictCursor
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Obtener datos de configuración de empresa
    cur.execute("""
        SELECT clave, valor 
        FROM configuracion 
        WHERE clave LIKE 'empresa_%' OR clave LIKE 'dian_%'
    """)
    config_rows = cur.fetchall()
    config = {row['clave']: row['valor'] for row in config_rows}
    
    # Obtener datos de factura
    cur.execute("""
        SELECT 
            f.*,
            t.nombres || ' ' || COALESCE(t.apellidos, '') as cliente_nombre,
            t.tipo_identificacion,
            t.numero_identificacion,
            t.digito_verificacion as cliente_dv,
            t.direccion as cliente_direccion,
            t.telefono as cliente_telefono,
            t.correo as cliente_email,
            t.regimen as cliente_regimen
        FROM facturas f
        LEFT JOIN terceros t ON f.tercero_id = t.id
        WHERE f.id = %s
    """, (factura_id,))
    
    factura = cur.fetchone()
    
    if not factura:
        raise ValueError(f"Factura {factura_id} no encontrada")
    
    # Obtener items de factura
    cur.execute("""
        SELECT 
            df.*,
            p.nombre as producto_nombre,
            p.impuesto_porcentaje
        FROM detalle_factura df
        LEFT JOIN productos p ON df.producto_id = p.id
        WHERE df.factura_id = %s
        ORDER BY df.id
    """, (factura_id,))
    
    items_rows = cur.fetchall()
    
    # Calcular totales
    subtotal = 0
    iva_total = 0
    
    items = []
    for item in items_rows:
        cantidad = float(item['cantidad'])
        precio = float(item['precio'])
        valor_impuesto = item.get('impuesto_porcentaje', 19)
        iva_porcentaje = float(valor_impuesto if valor_impuesto is not None else 19)
        
        precio_sin_iva = precio / (1 + (iva_porcentaje / 100))
        subtotal_item = precio_sin_iva * cantidad
        iva_item = (precio - precio_sin_iva) * cantidad
        total_item = precio * cantidad
        
        subtotal += subtotal_item
        iva_total += iva_item
        
        items.append({
            'nombre': item['producto_nombre'],
            'cantidad': cantidad,
            'precio_unitario': precio,
            'iva_porcentaje': iva_porcentaje,
            'total': total_item
        })
    
    total = subtotal + iva_total
    
    # Construir diccionario de datos
    data = {
        'id': factura['id'],
        'numero': factura['numero'],
        'prefijo': factura.get('prefijo', ''),
        'fecha': factura['fecha'].strftime('%Y-%m-%d') if factura['fecha'] else '',
        'cufe': factura.get('cufe', ''),
        'qr_code': factura.get('qr_code', ''),
        'forma_pago_nombre': 'Contado',  # TODO: Obtener de catálogo
        'medio_pago_nombre': 'Efectivo',  # TODO: Obtener de catálogo
        'empresa': {
            'nombre': config.get('empresa_razon_social', 'EMPRESA'),
            'nit': config.get('empresa_nit', ''),
            'digito_verificacion': config.get('empresa_digito_verificacion', ''),
            'direccion': config.get('empresa_direccion', ''),
            'municipio': config.get('empresa_municipio', ''),
            'telefono': config.get('empresa_telefono', ''),
            'email': config.get('empresa_email', ''),
            'regimen_nombre': 'Régimen Común',  # TODO: Obtener de catálogo
            'resolucion_numero': config.get('dian_resolucion_numero', ''),
            'resolucion_fecha': config.get('dian_resolucion_fecha', ''),
            'rango_desde': config.get('dian_rango_desde', ''),
            'rango_hasta': config.get('dian_rango_hasta', ''),
        },
        'cliente': {
            'nombre': factura['cliente_nombre'],
            'tipo_identificacion_nombre': 'NIT',  # TODO: Obtener de catálogo
            'numero_identificacion': factura.get('numero_identificacion', ''),
            'digito_verificacion': factura.get('cliente_dv', ''),
            'direccion': factura.get('cliente_direccion', ''),
            'telefono': factura.get('cliente_telefono', ''),
            'email': factura.get('cliente_email', ''),
            'regimen_nombre': 'Régimen Simplificado',  # TODO: Obtener de catálogo
        },
        'items': items,
        'totales': {
            'subtotal': subtotal,
            'iva': iva_total,
            'total': total
        }
    }
    
    return data


# ======================================================================
# EJEMPLO DE USO
# ======================================================================

if __name__ == "__main__":
    print("Módulo de generación de PDFs de facturas electrónicas")
    print("Importa este módulo en tu app.py")
