# app.py
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import sqlite3
from datetime import datetime
from collections import defaultdict
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "clave_secreta_super_segura"

DB_FILE = "pos.db"

# ===== CONEXIÓN DB =====
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# =========================
# FUNCIONES AUXILIARES CONTABILIDAD
# =========================
def crear_asiento_venta(factura_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        factura = cur.execute("SELECT numero, fecha, total FROM facturas WHERE id = ?", (factura_id,)).fetchone()
        if not factura:
            conn.close()
            return
        fecha = factura["fecha"]
        total = factura["total"]
        descripcion = f"Venta factura #{factura['numero']}"
        caja = cur.execute("SELECT id FROM puc WHERE codigo = '1105'").fetchone()
        ventas = cur.execute("SELECT id FROM puc WHERE codigo = '4135'").fetchone()
        if caja and ventas:
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, ?, 0, 'ventas', ?)""",
                        (fecha, caja["id"], descripcion, total, factura_id))
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, 0, ?, 'ventas', ?)""",
                        (fecha, ventas["id"], descripcion, total, factura_id))
        conn.commit()
    except Exception as e:
        print("Error creando asiento de venta:", e)
    finally:
        conn.close()

def crear_asiento_compra(compra_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        compra = cur.execute("SELECT numero, fecha, total, forma_pago FROM compras WHERE id = ?", (compra_id,)).fetchone()
        if not compra:
            conn.close()
            return
        fecha = compra["fecha"]
        total = compra["total"]
        descripcion = f"Compra #{compra['numero']}"
        inventario = cur.execute("SELECT id FROM puc WHERE codigo = '1435'").fetchone()
        if compra["forma_pago"] == "contado":
            pago = cur.execute("SELECT id FROM puc WHERE codigo = '1105'").fetchone()
        else:
            pago = cur.execute("SELECT id FROM puc WHERE codigo = '2205'").fetchone()
        if inventario and pago:
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, ?, 0, 'compras', ?)""",
                        (fecha, inventario["id"], descripcion, total, compra_id))
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, 0, ?, 'compras', ?)""",
                        (fecha, pago["id"], descripcion, total, compra_id))
        conn.commit()
    except Exception as e:
        print("Error creando asiento de compra:", e)
    finally:
        conn.close()

def crear_asiento_recibo(recibo_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        recibo = cur.execute("SELECT numero, fecha, valor, concepto FROM recibos_caja WHERE id = ?", (recibo_id,)).fetchone()
        if not recibo:
            conn.close()
            return
        descripcion = f"Recibo de Caja #{recibo['numero']} - {recibo['concepto'] or ''}"
        caja = cur.execute("SELECT id FROM puc WHERE codigo = '1105'").fetchone()
        ingreso = cur.execute("SELECT id FROM puc WHERE codigo = '4199'").fetchone()  # Otros ingresos
        if caja and ingreso:
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, ?, 0, 'recibo_caja', ?)""",
                        (recibo["fecha"], caja["id"], descripcion, recibo["valor"], recibo_id))
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, 0, ?, 'recibo_caja', ?)""",
                        (recibo["fecha"], ingreso["id"], descripcion, recibo["valor"], recibo_id))
        conn.commit()
    except Exception as e:
        print("Error asiento recibo:", e)
    finally:
        conn.close()

def crear_asiento_egreso(egreso_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        egreso = cur.execute("SELECT numero, fecha, valor, concepto FROM comprobantes_egreso WHERE id = ?", (egreso_id,)).fetchone()
        if not egreso:
            conn.close()
            return
        descripcion = f"Comprobante Egreso #{egreso['numero']} - {egreso['concepto'] or ''}"
        caja = cur.execute("SELECT id FROM puc WHERE codigo = '1105'").fetchone()
        gasto = cur.execute("SELECT id FROM puc WHERE codigo = '5195'").fetchone()  # Gastos varios
        if caja and gasto:
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, ?, 0, 'egreso', ?)""",
                        (egreso["fecha"], gasto["id"], descripcion, egreso["valor"], egreso_id))
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, 0, ?, 'egreso', ?)""",
                        (egreso["fecha"], caja["id"], descripcion, egreso["valor"], egreso_id))
        conn.commit()
    except Exception as e:
        print("Error asiento egreso:", e)
    finally:
        conn.close()

def crear_asiento_nota_credito(nota_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        nota = cur.execute("SELECT numero, fecha, total FROM notas_credito WHERE id = ?", (nota_id,)).fetchone()
        if not nota:
            conn.close()
            return
        fecha = nota["fecha"]
        total = nota["total"]
        descripcion = f"Nota Crédito #{nota['numero']}"
        ventas = cur.execute("SELECT id FROM puc WHERE codigo = '4135'").fetchone()  # Ventas
        devoluciones = cur.execute("SELECT id FROM puc WHERE codigo = '4175'").fetchone()  # Devoluciones en ventas
        if ventas and devoluciones:
            # Disminuye ventas
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, ?, 0, 'notas_credito', ?)""",
                        (fecha, ventas["id"], descripcion, total, nota_id))
            # Reconoce devolución
            cur.execute("""INSERT INTO movimientos_contables
                           (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                           VALUES (?, ?, ?, 0, ?, 'notas_credito', ?)""",
                        (fecha, devoluciones["id"], descripcion, total, nota_id))
        conn.commit()
    except Exception as e:
        print("Error asiento nota crédito:", e)
    finally:
        conn.close()

# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "").strip()

        # Intentar autenticar contra tabla usuarios (hash)
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            user = cur.execute("SELECT id, usuario, clave, rol, activo FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
            conn.close()
        except Exception:
            user = None

        # Si existe usuario en tabla usuarios: validar hash
        if user:
            try:
                if user["activo"] == 1 and check_password_hash(user["clave"], clave):
                    session["user"] = user["usuario"]
                    session["rol"] = user["rol"]
                    return redirect(url_for("facturacion"))
                else:
                    return render_template("login.html", error="Usuario o clave incorrectos")
            except Exception:
                # En caso de que la clave en DB no sea hashable (por compatibilidad), intentar comparación directa
                if user["activo"] == 1 and user["clave"] == clave:
                    session["user"] = user["usuario"]
                    session["rol"] = user["rol"]
                    return redirect(url_for("facturacion"))
                return render_template("login.html", error="Usuario o clave incorrectos")

        # Fallback: permitir admin/1234 si no existe tabla/usuario aún (temporal)
        if usuario == "admin" and clave == "1234":
            session["user"] = "admin"
            session["rol"] = "admin"
            return redirect(url_for("facturacion"))

        return render_template("login.html", error="Usuario o clave incorrectos")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================
# FACTURACIÓN
# =========================
@app.route("/facturacion")
def facturacion():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        clientes = cur.execute("""
            SELECT id, nombres || ' ' || IFNULL(apellidos,'') as nombre
            FROM terceros WHERE tipo='Cliente'
        """).fetchall()
    except Exception:
        clientes = []
    try:
        productos = cur.execute("SELECT id, nombre, stock, costo, precio FROM productos").fetchall()
    except Exception:
        productos = []
    try:
        cur.execute("SELECT MAX(numero) FROM facturas")
        last_num = cur.fetchone()[0] or 0
    except Exception:
        last_num = 0
    conn.close()

    return render_template(
        "facturacion.html",
        user=session["user"],
        clientes=clientes,
        productos=productos,
        factura_num=last_num + 1,
        fecha=datetime.now().strftime("%Y-%m-%d")
    )

@app.route("/facturacion/save", methods=["POST"])
def facturacion_save():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        tercero_id = data.get("cliente_id")
        factura_num = data.get("factura_num")
        fecha = data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
        lineas = data.get("lines", [])
        total = sum(float(l.get("total", 0)) for l in lineas)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO facturas (tercero_id, numero, fecha, total) VALUES (?, ?, ?, ?)", (tercero_id, factura_num, fecha, total))
        factura_id = cur.lastrowid
        for l in lineas:
            cur.execute("INSERT INTO detalle_factura (factura_id, producto_id, cantidad, precio, total) VALUES (?, ?, ?, ?, ?)",
                        (factura_id, l["producto_id"], l["cantidad"], l["precio"], l["total"]))
            cur.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (l["cantidad"], l["producto_id"]))
        conn.commit()
        conn.close()

        crear_asiento_venta(factura_id)

        return jsonify({"success": True, "factura_num": factura_num})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# FACTURAS Y NOTAS DE CRÉDITO
# =========================
@app.route("/facturas")
def facturas():
    """Lista de facturas con opción de ver detalle"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        facturas = cur.execute("""
            SELECT f.id, f.numero, f.fecha, f.total, 
                   t.nombres || ' ' || IFNULL(t.apellidos,'') as cliente
            FROM facturas f 
            LEFT JOIN terceros t ON f.tercero_id = t.id
            ORDER BY f.fecha DESC, f.numero DESC
        """).fetchall()
    except Exception:
        facturas = []
    conn.close()
    
    return render_template("lista_facturas.html", user=session["user"], facturas=facturas)

@app.route("/factura/<int:factura_id>")
def ver_factura(factura_id):
    """Ver detalle de una factura específica"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Obtener factura
        factura = cur.execute("""
            SELECT f.*, t.nombres, t.apellidos, t.telefono, t.direccion
            FROM facturas f 
            LEFT JOIN terceros t ON f.tercero_id = t.id 
            WHERE f.id = ?
        """, (factura_id,)).fetchone()
        
        if not factura:
            conn.close()
            return redirect(url_for("facturas"))
        
        # Obtener tercero
        tercero = cur.execute("""
            SELECT nombres, apellidos, telefono, direccion
            FROM terceros WHERE id = ?
        """, (factura["tercero_id"],)).fetchone()
        
        # Obtener detalle
        detalle = cur.execute("""
            SELECT df.cantidad, df.precio, df.total, p.nombre as producto
            FROM detalle_factura df 
            JOIN productos p ON df.producto_id = p.id
            WHERE df.factura_id = ?
        """, (factura_id,)).fetchall()
        
        # Obtener notas de crédito asociadas
        notas_credito = cur.execute("""
            SELECT nc.numero, nc.fecha, nc.total, nc.motivo
            FROM notas_credito nc
            WHERE nc.factura_id = ?
            ORDER BY nc.fecha DESC
        """, (factura_id,)).fetchall()
        
    except Exception as e:
        conn.close()
        return redirect(url_for("facturas"))
    
    conn.close()
    return render_template("factura_detalle.html", 
                         user=session["user"], 
                         factura=factura, 
                         tercero=tercero,
                         detalle=detalle,
                         notas_credito=notas_credito)

@app.route("/nota_credito/<int:factura_id>")
def crear_nota_credito(factura_id):
    """Crear nota de crédito para una factura"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Obtener factura
        factura = cur.execute("""
            SELECT f.*, t.nombres, t.apellidos
            FROM facturas f 
            LEFT JOIN terceros t ON f.tercero_id = t.id 
            WHERE f.id = ?
        """, (factura_id,)).fetchone()
        
        if not factura:
            conn.close()
            return redirect(url_for("facturas"))
        
        # Obtener detalle de la factura
        detalle = cur.execute("""
            SELECT df.producto_id, df.cantidad, df.precio, p.nombre as descripcion
            FROM detalle_factura df 
            JOIN productos p ON df.producto_id = p.id
            WHERE df.factura_id = ?
        """, (factura_id,)).fetchall()
        
        # Obtener próximo número de nota de crédito
        cur.execute("SELECT MAX(numero) FROM notas_credito")
        last_num = cur.fetchone()[0] or 0
        next_num = last_num + 1
        
    except Exception as e:
        conn.close()
        return redirect(url_for("facturas"))
    
    conn.close()
    return render_template("nota_credito.html", 
                         user=session["user"],
                         factura=factura,
                         detalle=detalle,
                         next_num=next_num)

@app.route("/nota_credito/save", methods=["POST"])
def save_nota_credito():
    """Guardar nota de crédito"""
    if "user" not in session:
        return redirect(url_for("login"))
    
    try:
        factura_id = request.form.get("factura_id")
        numero = request.form.get("numero")
        fecha = request.form.get("fecha")
        motivo = request.form.get("motivo")
        
        # Obtener arrays de detalle
        producto_ids = request.form.getlist("producto_id[]")
        descripciones = request.form.getlist("descripcion[]")
        cantidades = request.form.getlist("cantidad[]")
        precios = request.form.getlist("precio[]")
        totales_linea = request.form.getlist("total_linea[]")
        
        total_nota = float(request.form.get("total", 0))
        
        if total_nota <= 0:
            return redirect(url_for("crear_nota_credito", factura_id=factura_id))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Obtener tercero de la factura
        factura_info = cur.execute("SELECT tercero_id FROM facturas WHERE id = ?", (factura_id,)).fetchone()
        tercero_id = factura_info["tercero_id"] if factura_info else None
        
        # Insertar nota de crédito
        cur.execute("""
            INSERT INTO notas_credito (factura_id, numero, fecha, tercero_id, motivo, total, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (factura_id, numero, fecha, tercero_id, motivo, total_nota, session["user"]))
        
        nota_id = cur.lastrowid
        
        # Insertar detalle y devolver inventario
        for i in range(len(producto_ids)):
            cantidad = float(cantidades[i]) if cantidades[i] else 0
            if cantidad > 0:
                precio = float(precios[i])
                total_linea = float(totales_linea[i])
                
                # Insertar línea de detalle
                cur.execute("""
                    INSERT INTO detalle_nota_credito 
                    (nota_id, producto_id, descripcion, cantidad, precio, total)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nota_id, producto_ids[i], descripciones[i], cantidad, precio, total_linea))
                
                # Devolver inventario
                cur.execute("""
                    UPDATE productos SET stock = stock + ? WHERE id = ?
                """, (cantidad, producto_ids[i]))
        
        conn.commit()
        conn.close()
        
        # Crear asiento contable
        crear_asiento_nota_credito(nota_id)
        
        return redirect(url_for("ver_factura", factura_id=factura_id))
        
    except Exception as e:
        return redirect(url_for("crear_nota_credito", factura_id=factura_id))

# =========================
# COMPRAS
# =========================
@app.route("/compras")
def compras():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        proveedores = cur.execute("SELECT id, nombres || ' ' || IFNULL(apellidos,'') as nombre FROM terceros WHERE tipo='Proveedor'").fetchall()
    except Exception:
        proveedores = []
    try:
        productos = cur.execute("SELECT id, nombre, stock, costo FROM productos").fetchall()
    except Exception:
        productos = []
    try:
        cur.execute("SELECT MAX(id) FROM compras")
        last_num = cur.fetchone()[0] or 0
    except Exception:
        last_num = 0
    conn.close()

    return render_template("compras.html", user=session["user"], proveedores=proveedores, productos=productos, compra_num=last_num + 1, fecha=datetime.now().strftime("%Y-%m-%d"))

@app.route("/compras/save", methods=["POST"])
def compras_save():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401

    try:
        data = request.get_json()
        proveedor_id = data.get("proveedor_id")
        numero = data.get("numero")
        fecha = data.get("fecha")
        forma_pago = data.get("forma_pago")
        lines = data.get("lines", [])

        total = sum(float(l["total"]) for l in lines)

        conn = get_db_connection()
        cur = conn.cursor()

        # Cabecera
        cur.execute("""
            INSERT INTO compras (tercero_id, numero, fecha, total, forma_pago, pagada)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (proveedor_id, numero, fecha, total, forma_pago, 1 if forma_pago=="contado" else 0))
        compra_id = cur.lastrowid

        # Detalle y actualización de inventario
        for l in lines:
            cur.execute("""
                INSERT INTO detalle_compra (compra_id, producto_id, cantidad, costo, total)
                VALUES (?, ?, ?, ?, ?)
            """, (compra_id, l["producto_id"], l["cantidad"], l["costo"], l["total"]))

            cur.execute("""
                UPDATE productos
                SET stock = stock + ?, costo = ?
                WHERE id = ?
            """, (l["cantidad"], l["costo"], l["producto_id"]))

        conn.commit()
        conn.close()

        return jsonify({"success": True, "compra_num": numero})
    except Exception as e:
        print("Error en compras_save:", e)
        return jsonify({"success": False, "error": str(e)})

# =========================
# INVENTARIO
# =========================
@app.route("/inventario")
def inventario():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        productos_raw = cur.execute("SELECT id, nombre, stock, costo, precio FROM productos").fetchall()
    except Exception:
        productos_raw = []
    conn.close()
    productos = [{"id": p[0], "nombre": p[1], "stock": p[2], "costo": p[3], "precio": p[4]} for p in productos_raw]
    return render_template("inventario.html", user=session["user"], productos=productos)

@app.route("/add_producto", methods=["POST"])
def add_producto():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        nombre = data.get("nombre", "").strip()
        stock = float(data.get("stock", 0))
        costo = float(data.get("costo", 0))
        precio = float(data.get("precio", 0))
        if not nombre:
            return jsonify({"success": False, "error": "Nombre requerido"})
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO productos (nombre, stock, costo, precio) VALUES (?, ?, ?, ?)", (nombre, stock, costo, precio))
        conn.commit()
        nuevo_id = cur.lastrowid
        conn.close()
        return jsonify({"success": True, "id": nuevo_id, "mensaje": f"Producto '{nombre}' agregado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/update_producto/<int:producto_id>", methods=["PUT"])
def update_producto(producto_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        nombre = data.get("nombre", "").strip()
        stock = float(data.get("stock", 0))
        costo = float(data.get("costo", 0))
        precio = float(data.get("precio", 0))
        if not nombre:
            return jsonify({"success": False, "error": "Nombre requerido"})
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE productos SET nombre=?, stock=?, costo=?, precio=? WHERE id=?", (nombre, stock, costo, precio, producto_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "mensaje": "Producto actualizado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/delete_producto/<int:producto_id>", methods=["DELETE"])
def delete_producto(producto_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM productos WHERE id=?", (producto_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "mensaje": "Producto eliminado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# API / DEBUG: listar productos (útil para verificar DB)
# =========================
@app.route("/api/productos")
def api_productos():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        prows = cur.execute("SELECT id, nombre, stock, costo, precio FROM productos ORDER BY nombre").fetchall()
        productos = [dict(p) for p in prows]
    except Exception as e:
        print("Error en api_productos:", e)
        productos = []
    conn.close()
    return jsonify(productos)


# =========================
# TRANSFORMACIONES DE INVENTARIO
# =========================
@app.route("/transformaciones")
def transformaciones():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        prows = cur.execute("SELECT id, nombre, stock, costo, precio FROM productos ORDER BY nombre").fetchall()
        productos = [dict(p) for p in prows]
        trows = cur.execute("""
            SELECT id, numero, fecha, descripcion, total_salida, total_entrada, creado_por
            FROM transformaciones
            ORDER BY fecha DESC, id DESC
        """).fetchall()
        transformaciones = [dict(t) for t in trows]
    except Exception as e:
        print("Error cargando transformaciones:", e)
        productos, transformaciones = [], []
    finally:
        conn.close()

    # pasar fecha de hoy para el template
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    return render_template("transformaciones.html",
                           user=session["user"],
                           productos=productos,
                           transformaciones=transformaciones,
                           fecha_hoy=fecha_hoy)


@app.route("/transformaciones/save", methods=["POST"])
def save_transformacion():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401

    try:
        data = request.get_json() or {}
        fecha = data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
        descripcion = data.get("descripcion", "")
        salidas = data.get("salidas", [])   # [{producto_id, cantidad}]
        entradas = data.get("entradas", []) # [{producto_id, cantidad, costo}]

        total_salida = 0.0
        total_entrada = 0.0

        conn = get_db_connection()
        cur = conn.cursor()

        # ✅ Consecutivo automático
        cur.execute("SELECT IFNULL(MAX(numero), 0) + 1 AS next_num FROM transformaciones")
        row = cur.fetchone()
        numero = row["next_num"]

        # Insertar cabecera
        cur.execute("""
            INSERT INTO transformaciones (numero, fecha, descripcion, total_salida, total_entrada, creado_por)
            VALUES (?, ?, ?, 0, 0, ?)
        """, (numero, fecha, descripcion, session["user"]))
        trans_id = cur.lastrowid

        # Registrar salidas (disminuye stock)
        for s in salidas:
            pid = int(s.get("producto_id"))
            cant = float(s.get("cantidad") or 0)
            if cant <= 0:
                continue
            prod = cur.execute("SELECT costo FROM productos WHERE id=?", (pid,)).fetchone()
            costo_unit = float(prod["costo"]) if prod and prod["costo"] is not None else 0.0
            total = cant * costo_unit
            total_salida += total

            cur.execute("""
                INSERT INTO detalle_transformacion (transformacion_id, tipo, producto_id, cantidad, costo, total)
                VALUES (?, 'salida', ?, ?, ?, ?)
            """, (trans_id, pid, cant, costo_unit, total))

            cur.execute("UPDATE productos SET stock = stock - ? WHERE id=?", (cant, pid))

        # Registrar entradas (aumenta stock)
        for e in entradas:
            pid = int(e.get("producto_id"))
            cant = float(e.get("cantidad") or 0)
            costo_unit = float(e.get("costo") or 0)
            if cant <= 0:
                continue
            total = cant * costo_unit
            total_entrada += total

            cur.execute("""
                INSERT INTO detalle_transformacion (transformacion_id, tipo, producto_id, cantidad, costo, total)
                VALUES (?, 'entrada', ?, ?, ?, ?)
            """, (trans_id, pid, cant, costo_unit, total))

            cur.execute("UPDATE productos SET stock = stock + ?, costo = ? WHERE id = ?", (cant, costo_unit, pid))

        # Actualizar totales
        cur.execute("UPDATE transformaciones SET total_salida=?, total_entrada=? WHERE id=?",
                    (total_salida, total_entrada, trans_id))

        conn.commit()
        conn.close()

        # Registrar asiento contable 1435 contra 1435
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            inventario = cur.execute("SELECT id FROM puc WHERE codigo='1435'").fetchone()
            if inventario:
                cur.execute("""
                    INSERT INTO movimientos_contables (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                    VALUES (?, ?, ?, ?, 0, 'transformacion', ?)
                """, (fecha, inventario["id"], f"Transformación {numero}", total_entrada, trans_id))
                cur.execute("""
                    INSERT INTO movimientos_contables (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                    VALUES (?, ?, ?, 0, ?, 'transformacion', ?)
                """, (fecha, inventario["id"], f"Transformación {numero}", total_salida, trans_id))
                conn.commit()
            conn.close()
        except Exception as e:
            print("Error asiento transformación:", e)

        return jsonify({"success": True, "mensaje": f"Transformación #{numero} registrada"})
    except Exception as e:
        print("Error save_transformacion:", e)
        return jsonify({"success": False, "error": str(e)})


# =========================
# TERCEROS
# =========================
@app.route("/tercero/add", methods=["POST"])
def add_tercero():
    if "user" not in session:
        return redirect(url_for("login"))
    data = request.get_json()
    try:
        nombres = data.get("nombres")
        apellidos = data.get("apellidos")
        telefono = data.get("telefono")
        correo = data.get("correo")
        direccion = data.get("direccion")
        tipo = data.get("tipo")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO terceros (nombres, apellidos, telefono, correo, direccion, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                    (nombres, apellidos, telefono, correo, direccion, tipo))
        conn.commit()
        tercero_id = cur.lastrowid
        conn.close()
        return jsonify({"success": True, "id": tercero_id, "nombre": f"{nombres} {apellidos}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# GASTOS (vista)
# =========================
@app.route("/gastos")
def gastos():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("gastos.html", user=session["user"])

# =========================
# RECIBOS DE CAJA
# =========================
@app.route("/recibo_caja")
def recibo_caja():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        terceros = cur.execute("SELECT id, nombres || ' ' || IFNULL(apellidos,'') as nombre FROM terceros").fetchall()
    except Exception:
        terceros = []
    try:
        cur.execute("SELECT MAX(numero) FROM recibos_caja")
        last_num = cur.fetchone()[0] or 0
    except Exception:
        last_num = 0
    conn.close()
    return render_template("recibo_caja.html", user=session["user"], clientes=terceros, numero=last_num + 1, fecha=datetime.now().strftime("%Y-%m-%d"))

@app.route("/recibo_caja/save", methods=["POST"])
def recibo_caja_save():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        tercero_id = data.get("tercero_id")
        numero = data.get("numero")
        fecha = data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
        concepto = data.get("concepto")
        valor = float(data.get("valor"))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO recibos_caja (numero, fecha, tercero_id, concepto, valor) VALUES (?, ?, ?, ?, ?)",
                    (numero, fecha, tercero_id, concepto, valor))
        recibo_id = cur.lastrowid
        conn.commit()
        conn.close()
        crear_asiento_recibo(recibo_id)
        return jsonify({"success": True, "recibo_num": numero})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/recibos/lista", methods=["POST"])
def api_recibos_lista():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        recibos = cur.execute("""
            SELECT r.id, r.numero, r.fecha, r.concepto, r.valor,
                   t.nombres || ' ' || IFNULL(t.apellidos,'') as tercero
            FROM recibos_caja r
            LEFT JOIN terceros t ON r.tercero_id = t.id
            WHERE r.fecha BETWEEN ? AND ?
            ORDER BY r.fecha DESC, r.numero DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        return jsonify({"success": True, "recibos": [dict(row) for row in recibos]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# COMPROBANTES DE EGRESO
# =========================
@app.route("/comprobante_egreso")
def comprobante_egreso():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        terceros = cur.execute("SELECT id, nombres || ' ' || IFNULL(apellidos,'') as nombre FROM terceros").fetchall()
    except Exception:
        terceros = []
    try:
        cur.execute("SELECT MAX(numero) FROM comprobantes_egreso")
        last_num = cur.fetchone()[0] or 0
    except Exception:
        last_num = 0
    conn.close()
    return render_template("comprobante_egreso.html", user=session["user"], terceros=terceros, numero=last_num + 1, fecha=datetime.now().strftime("%Y-%m-%d"))

@app.route("/comprobante_egreso/save", methods=["POST"])
def comprobante_egreso_save():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        tercero_id = data.get("tercero_id")
        numero = data.get("numero")
        fecha = data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
        concepto = data.get("concepto")
        valor = float(data.get("valor"))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO comprobantes_egreso (numero, fecha, tercero_id, concepto, valor) VALUES (?, ?, ?, ?, ?)",
                    (numero, fecha, tercero_id, concepto, valor))
        egreso_id = cur.lastrowid
        conn.commit()
        conn.close()
        crear_asiento_egreso(egreso_id)
        return jsonify({"success": True, "egreso_num": numero})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/egresos/lista", methods=["POST"])
def api_egresos_lista():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        egresos = cur.execute("""
            SELECT e.id, e.numero, e.fecha, e.concepto, e.valor,
                   t.nombres || ' ' || IFNULL(t.apellidos,'') as tercero
            FROM comprobantes_egreso e
            LEFT JOIN terceros t ON e.tercero_id = t.id
            WHERE e.fecha BETWEEN ? AND ?
            ORDER BY e.fecha DESC, e.numero DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        return jsonify({"success": True, "egresos": [dict(row) for row in egresos]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# CONTABILIDAD
# =========================
@app.route("/contabilidad")
def contabilidad():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("contabilidad.html", user=session["user"])

@app.route("/contabilidad/puc")
def puc():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cuentas = cur.execute("SELECT codigo, nombre, tipo FROM puc ORDER BY codigo").fetchall()
    except Exception:
        cuentas = []
    conn.close()
    return render_template("puc.html", user=session["user"], cuentas=cuentas)

@app.route("/contabilidad/movimientos")
def movimientos():
    if "user" not in session:
        return redirect(url_for("login"))
    today = datetime.now().strftime("%Y-%m-%d")
    first_day_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    return render_template("movimientos.html", user=session["user"], fecha_inicio=first_day_month, fecha_fin=today)

@app.route("/api/puc/add", methods=["POST"])
def add_cuenta():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        codigo = data.get("codigo", "").strip()
        nombre = data.get("nombre", "").strip()
        tipo = data.get("tipo", "").strip()
        if not all([codigo, nombre, tipo]):
            return jsonify({"success": False, "error": "Todos los campos son obligatorios"})
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO puc (codigo, nombre, tipo) VALUES (?, ?, ?)", (codigo, nombre, tipo))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "mensaje": f"Cuenta {codigo} agregada correctamente"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "El código de cuenta ya existe"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/movimientos", methods=["POST"])
def get_movimientos():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        movimientos = cur.execute("""
            SELECT m.fecha, m.descripcion, p.codigo, p.nombre, m.debito, m.credito, m.modulo, m.referencia_id
            FROM movimientos_contables m
            JOIN puc p ON m.cuenta_id = p.id
            WHERE m.fecha BETWEEN ? AND ?
            ORDER BY m.fecha DESC, m.id DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        return jsonify({"success": True, "movimientos": [dict(row) for row in movimientos]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/balance", methods=["POST"])
def get_balance():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        balance = cur.execute("""
            SELECT p.codigo, p.nombre, p.tipo,
                   SUM(m.debito) as total_debito,
                   SUM(m.credito) as total_credito,
                   CASE WHEN p.tipo IN ('activo', 'gasto') THEN SUM(m.debito) - SUM(m.credito)
                        ELSE SUM(m.credito) - SUM(m.debito)
                   END as saldo
            FROM puc p
            LEFT JOIN movimientos_contables m ON p.id = m.cuenta_id AND m.fecha <= ?
            GROUP BY p.id, p.codigo, p.nombre, p.tipo
            HAVING SUM(COALESCE(m.debito,0)) > 0 OR SUM(COALESCE(m.credito,0)) > 0
            ORDER BY p.codigo
        """, (fecha_fin,)).fetchall()
        conn.close()
        return jsonify({"success": True, "balance": [dict(row) for row in balance]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/puc/seed", methods=["POST"])
def seed_puc():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    cuentas_basicas = [
        ("1105", "Caja", "activo"),
        ("1110", "Bancos", "activo"),
        ("1305", "Clientes", "activo"),
        ("1435", "Inventario de Mercancías", "activo"),
        ("1540", "Equipo de Oficina", "activo"),
        ("2205", "Proveedores", "pasivo"),
        ("2365", "Retención en la Fuente", "pasivo"),
        ("2404", "IVA por Pagar", "pasivo"),
        ("3105", "Capital Social", "patrimonio"),
        ("3605", "Utilidades Retenidas", "patrimonio"),
        ("4135", "Comercio al por Mayor y al Detal", "ingreso"),
        ("4175", "Devoluciones en Ventas", "ingreso"),
        ("4199", "Otros Ingresos", "ingreso"),
        ("5105", "Gastos de Personal", "gasto"),
        ("5135", "Servicios", "gasto"),
        ("5140", "Gastos Legales", "gasto"),
        ("5195", "Diversos", "gasto"),
        ("6135", "Comercio al por Mayor y al Detal", "gasto")
    ]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        for codigo, nombre, tipo in cuentas_basicas:
            cur.execute("INSERT OR IGNORE INTO puc (codigo, nombre, tipo) VALUES (?, ?, ?)", (codigo, nombre, tipo))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "mensaje": "PUC inicializado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# RESUMENES Y REPORTES
# =========================
@app.route("/resumenes")
def resumenes():
    if "user" not in session:
        return redirect(url_for("login"))
    today = datetime.now().strftime("%Y-%m-%d")
    first_day_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    return render_template("resumenes.html", user=session["user"], fecha_inicio=first_day_month, fecha_fin=today)

@app.route("/api/resumen/ventas", methods=["POST"])
def api_resumen_ventas():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        ventas_diarias = cur.execute("""
            SELECT DATE(fecha) as dia, COUNT(*) as num_facturas, SUM(total) as total_ventas
            FROM facturas WHERE fecha BETWEEN ? AND ? GROUP BY DATE(fecha) ORDER BY dia
        """, (fecha_inicio, fecha_fin)).fetchall()
        total_periodo = cur.execute("""
            SELECT COUNT(*) as facturas, SUM(total) as total, AVG(total) as promedio
            FROM facturas WHERE fecha BETWEEN ? AND ?
        """, (fecha_inicio, fecha_fin)).fetchone()
        producto_top = cur.execute("""
            SELECT p.nombre, SUM(df.cantidad) as cantidad_vendida, SUM(df.total) as ingresos_producto
            FROM detalle_factura df JOIN productos p ON df.producto_id = p.id
            JOIN facturas f ON df.factura_id = f.id
            WHERE f.fecha BETWEEN ? AND ? GROUP BY p.id, p.nombre ORDER BY cantidad_vendida DESC LIMIT 1
        """, (fecha_inicio, fecha_fin)).fetchone()
        top_productos = cur.execute("""
            SELECT p.nombre, SUM(df.cantidad) as cantidad_vendida, SUM(df.total) as ingresos_producto, COUNT(DISTINCT f.id) as facturas_aparece
            FROM detalle_factura df JOIN productos p ON df.producto_id = p.id JOIN facturas f ON df.factura_id = f.id
            WHERE f.fecha BETWEEN ? AND ? GROUP BY p.id, p.nombre ORDER BY cantidad_vendida DESC LIMIT 5
        """, (fecha_inicio, fecha_fin)).fetchall()
        cliente_top = cur.execute("""
            SELECT t.nombres || ' ' || IFNULL(t.apellidos,'') as cliente, COUNT(*) as num_compras, SUM(f.total) as total_comprado
            FROM facturas f JOIN terceros t ON f.tercero_id = t.id
            WHERE f.fecha BETWEEN ? AND ? GROUP BY t.id, cliente ORDER BY total_comprado DESC LIMIT 1
        """, (fecha_inicio, fecha_fin)).fetchone()
        conn.close()
        return jsonify({"success": True,
                        "ventas_diarias": [dict(r) for r in ventas_diarias],
                        "total_periodo": dict(total_periodo) if total_periodo else {},
                        "producto_top": dict(producto_top) if producto_top else {},
                        "top_productos": [dict(r) for r in top_productos],
                        "cliente_top": dict(cliente_top) if cliente_top else {}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/resumen/compras", methods=["POST"])
def api_resumen_compras():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        compras_diarias = cur.execute("""
            SELECT DATE(fecha) as dia, COUNT(*) as num_compras, SUM(total) as total_compras
            FROM compras WHERE fecha BETWEEN ? AND ? GROUP BY DATE(fecha) ORDER BY dia
        """, (fecha_inicio, fecha_fin)).fetchall()
        total_compras = cur.execute("""
            SELECT COUNT(*) as compras, SUM(total) as total, AVG(total) as promedio,
                   SUM(CASE WHEN pagada = 1 THEN total ELSE 0 END) as pagadas,
                   SUM(CASE WHEN pagada = 0 THEN total ELSE 0 END) as pendientes
            FROM compras WHERE fecha BETWEEN ? AND ?
        """, (fecha_inicio, fecha_fin)).fetchone()
        proveedor_top = cur.execute("""
            SELECT t.nombres || ' ' || IFNULL(t.apellidos,'') as proveedor, COUNT(*) as num_compras, SUM(c.total) as total_comprado
            FROM compras c JOIN terceros t ON c.tercero_id = t.id
            WHERE c.fecha BETWEEN ? AND ? GROUP BY t.id, proveedor ORDER BY total_comprado DESC LIMIT 1
        """, (fecha_inicio, fecha_fin)).fetchone()
        productos_comprados = cur.execute("""
            SELECT p.nombre, SUM(dc.cantidad) as cantidad_comprada, SUM(dc.total) as total_invertido, COUNT(DISTINCT c.id) as compras_aparece
            FROM detalle_compra dc JOIN productos p ON dc.producto_id = p.id JOIN compras c ON dc.compra_id = c.id
            WHERE c.fecha BETWEEN ? AND ? GROUP BY p.id, p.nombre ORDER BY cantidad_comprada DESC LIMIT 5
        """, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        return jsonify({"success": True,
                        "compras_diarias": [dict(r) for r in compras_diarias],
                        "total_compras": dict(total_compras) if total_compras else {},
                        "proveedor_top": dict(proveedor_top) if proveedor_top else {},
                        "productos_comprados": [dict(r) for r in productos_comprados]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/facturas/lista", methods=["POST"])
def api_facturas_lista():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        facturas = cur.execute("""
            SELECT f.id, f.numero, f.fecha, f.total, t.nombres || ' ' || IFNULL(t.apellidos,'') as cliente
            FROM facturas f LEFT JOIN terceros t ON f.tercero_id = t.id
            WHERE f.fecha BETWEEN ? AND ? ORDER BY f.fecha DESC, f.numero DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        return jsonify({"success": True, "facturas": [dict(r) for r in facturas]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/compras/lista", methods=["POST"])
def api_compras_lista():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio = data.get("fecha_inicio")
    fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        compras = cur.execute("""
            SELECT c.id, c.numero, c.fecha, c.total, c.forma_pago, c.pagada, t.nombres || ' ' || IFNULL(t.apellidos,'') as proveedor
            FROM compras c LEFT JOIN terceros t ON c.tercero_id = t.id
            WHERE c.fecha BETWEEN ? AND ? ORDER BY c.fecha DESC, c.numero DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        return jsonify({"success": True, "compras": [dict(r) for r in compras]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/factura/<int:factura_id>")
def api_factura_detalle(factura_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    try:
        conn = get_db_connection(); cur = conn.cursor()
        factura = cur.execute("""
            SELECT f.*, t.nombres || ' ' || IFNULL(t.apellidos,'') as cliente, t.telefono, t.direccion
            FROM facturas f LEFT JOIN terceros t ON f.tercero_id = t.id WHERE f.id = ?
        """, (factura_id,)).fetchone()
        if not factura:
            conn.close()
            return jsonify({"success": False, "error": "Factura no encontrada"})
        detalle = cur.execute("""
            SELECT df.cantidad, df.precio, df.total, p.nombre as producto
            FROM detalle_factura df JOIN productos p ON df.producto_id = p.id
            WHERE df.factura_id = ?
        """, (factura_id,)).fetchall()
        conn.close()
        return jsonify({"success": True, "factura": dict(factura), "detalle": [dict(r) for r in detalle]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/compra/<int:compra_id>")
def api_compra_detalle(compra_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    try:
        conn = get_db_connection(); cur = conn.cursor()
        compra = cur.execute("""
            SELECT c.*, t.nombres || ' ' || IFNULL(t.apellidos,'') as proveedor, t.telefono, t.direccion
            FROM compras c LEFT JOIN terceros t ON c.tercero_id = t.id WHERE c.id = ?
        """, (compra_id,)).fetchone()
        if not compra:
            conn.close()
            return jsonify({"success": False, "error": "Compra no encontrada"})
        detalle = cur.execute("""
            SELECT dc.cantidad, dc.costo, dc.total, p.nombre as producto
            FROM detalle_compra dc JOIN productos p ON dc.producto_id = p.id WHERE dc.compra_id = ?
        """, (compra_id,)).fetchall()
        conn.close()
        return jsonify({"success": True, "compra": dict(compra), "detalle": [dict(r) for r in detalle]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# AJUSTES (USUARIOS / CONFIG)
# =========================
@app.route("/ajustes")
def ajustes():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("ajustes.html", user=session["user"])

@app.route("/ajustes/usuarios")
def ajustes_usuarios():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection(); cur = conn.cursor()
    try:
        usuarios = cur.execute("SELECT id, usuario, rol, activo FROM usuarios ORDER BY id").fetchall()
    except Exception:
        usuarios = []
    conn.close()
    return render_template("usuarios.html", user=session["user"], usuarios=usuarios)

@app.route("/ajustes/usuarios/add", methods=["POST"])
def add_usuario():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    usuario = (data.get("usuario") or "").strip()
    clave = (data.get("clave") or "").strip()
    rol = data.get("rol") or "cajero"
    if not usuario or not clave:
        return jsonify({"success": False, "error": "usuario y clave requeridos"})
    try:
        conn = get_db_connection(); cur = conn.cursor()
        hashed = generate_password_hash(clave)
        cur.execute("INSERT INTO usuarios (usuario, clave, rol, activo) VALUES (?, ?, ?, 1)", (usuario, hashed, rol))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "mensaje": "Usuario creado"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "El usuario ya existe"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/ajustes/usuarios/toggle/<int:user_id>", methods=["POST"])
def toggle_usuario(user_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    try:
        conn = get_db_connection(); cur = conn.cursor()
        u = cur.execute("SELECT activo FROM usuarios WHERE id=?", (user_id,)).fetchone()
        if not u:
            conn.close()
            return jsonify({"success": False, "error": "Usuario no encontrado"})
        nuevo_estado = 0 if u["activo"] == 1 else 1
        cur.execute("UPDATE usuarios SET activo=? WHERE id=?", (nuevo_estado, user_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "estado": nuevo_estado})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# INICIO
# =========================
@app.route("/")
def index():
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)