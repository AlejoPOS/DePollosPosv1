import os
import re
import psycopg2
import sqlite3  # ✅ Para manejar excepciones sqlite3.IntegrityError
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------------------------------------------------------------
#  Conexión Postgres + compatibilidad placeholders SQLite -> PostgreSQL
# ----------------------------------------------------------------------

def _replace_placeholders(sql: str) -> str:
    """
    Reemplaza cada '?' por '%s' solo si está fuera de comillas simples o dobles.
    Además, convierte IFNULL en COALESCE para PostgreSQL.
    """
    sql = sql.replace("IFNULL", "COALESCE")  # ✅ PostgreSQL usa COALESCE

    out = []
    in_sq = False
    in_dq = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'" and not in_dq:
            in_sq = not in_sq
            out.append(c)
            i += 1
            continue
        if c == '"' and not in_sq:
            in_dq = not in_dq
            out.append(c)
            i += 1
            continue
        if c == '?' and not in_sq and not in_dq:
            out.append('%s')
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)

class CompatCursor:
    def __init__(self, real_cursor):
        self._cur = real_cursor

    def execute(self, query, params=None):
        if isinstance(query, str):
            query = _replace_placeholders(query)
        self._cur.execute(query, params)
        return self

    def executemany(self, query, seq_of_params):
        if isinstance(query, str):
            query = _replace_placeholders(query)
        return self._cur.executemany(query, seq_of_params)

    def fetchone(self):
        row = self._cur.fetchone()
        return row if row is None else dict(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [dict(r) for r in rows]

    def __getattr__(self, name):
        return getattr(self._cur, name)

class CompatConnection:
    def __init__(self, real_conn):
        self._conn = real_conn

    def cursor(self, *args, **kwargs):
        real_cursor = self._conn.cursor(*args, **kwargs)
        return CompatCursor(real_cursor)

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db_connection():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL no está definida en las variables de entorno")


    real_conn = psycopg2.connect(
        dsn,
        sslmode="require",
        cursor_factory=RealDictCursor
    )
    return CompatConnection(real_conn)

# ----------------------------------------------------------------------
#  CREACIÓN DE LA APLICACIÓN FLASK
# ----------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta_por_defecto")


# ===== CONEXIÓN DB =====
def get_db_connection():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL no está definida en las variables de entorno")

    real_conn = psycopg2.connect(
        dsn,
        sslmode="require",
        cursor_factory=RealDictCursor
    )
    return CompatConnection(real_conn)

# =========================
# FUNCIONES AUXILIARES CONTABILIDAD
# =========================
def crear_asiento_venta(factura_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        factura = cur.execute(
            "SELECT numero, fecha, total FROM facturas WHERE id = %s", (factura_id,)
        ).fetchone()
        if not factura:
            conn.close()
            return
        fecha = factura["fecha"]
        total = factura["total"]
        descripcion = f"Venta factura #{factura['numero']}"
        caja = cur.execute("SELECT id FROM puc WHERE codigo = '1105'").fetchone()
        ventas = cur.execute("SELECT id FROM puc WHERE codigo = '4135'").fetchone()
        if caja and ventas:
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, %s, 0, 'ventas', %s)""",
                (fecha, caja["id"], descripcion, total, factura_id),
            )
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, 0, %s, 'ventas', %s)""",
                (fecha, ventas["id"], descripcion, total, factura_id),
            )
        conn.commit()
    except Exception as e:
        print("Error creando asiento de venta:", e)
    finally:
        conn.close()


def crear_asiento_compra(compra_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        compra = cur.execute(
            "SELECT numero, fecha, total, forma_pago FROM compras WHERE id = %s",
            (compra_id,),
        ).fetchone()
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
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, %s, 0, 'compras', %s)""",
                (fecha, inventario["id"], descripcion, total, compra_id),
            )
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, 0, %s, 'compras', %s)""",
                (fecha, pago["id"], descripcion, total, compra_id),
            )
        conn.commit()
    except Exception as e:
        print("Error creando asiento de compra:", e)
    finally:
        conn.close()


def crear_asiento_recibo(recibo_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        recibo = cur.execute(
            "SELECT numero, fecha, valor, concepto FROM recibos_caja WHERE id = %s",
            (recibo_id,),
        ).fetchone()
        if not recibo:
            conn.close()
            return
        descripcion = f"Recibo de Caja #{recibo['numero']} - {recibo['concepto'] or ''}"
        caja = cur.execute("SELECT id FROM puc WHERE codigo = '1105'").fetchone()
        ingreso = cur.execute("SELECT id FROM puc WHERE codigo = '4199'").fetchone()  # Otros ingresos
        if caja and ingreso:
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, %s, 0, 'recibo_caja', %s)""",
                (recibo["fecha"], caja["id"], descripcion, recibo["valor"], recibo_id),
            )
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, 0, %s, 'recibo_caja', %s)""",
                (recibo["fecha"], ingreso["id"], descripcion, recibo["valor"], recibo_id),
            )
        conn.commit()
    except Exception as e:
        print("Error asiento recibo:", e)
    finally:
        conn.close()


def crear_asiento_egreso(egreso_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        egreso = cur.execute(
            "SELECT numero, fecha, valor, concepto FROM comprobantes_egreso WHERE id = %s",
            (egreso_id,),
        ).fetchone()
        if not egreso:
            conn.close()
            return
        descripcion = f"Comprobante Egreso #{egreso['numero']} - {egreso['concepto'] or ''}"
        caja = cur.execute("SELECT id FROM puc WHERE codigo = '1105'").fetchone()
        gasto = cur.execute("SELECT id FROM puc WHERE codigo = '5195'").fetchone()  # Gastos varios
        if caja and gasto:
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, %s, 0, 'egreso', %s)""",
                (egreso["fecha"], gasto["id"], descripcion, egreso["valor"], egreso_id),
            )
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, 0, %s, 'egreso', %s)""",
                (egreso["fecha"], caja["id"], descripcion, egreso["valor"], egreso_id),
            )
        conn.commit()
    except Exception as e:
        print("Error asiento egreso:", e)
    finally:
        conn.close()


def crear_asiento_nota_credito(nota_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        nota = cur.execute(
            "SELECT numero, fecha, total FROM notas_credito WHERE id = %s",
            (nota_id,),
        ).fetchone()
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
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, %s, 0, 'notas_credito', %s)""",
                (fecha, ventas["id"], descripcion, total, nota_id),
            )
            # Reconoce devolución
            cur.execute(
                """INSERT INTO movimientos_contables
                   (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                   VALUES (%s, %s, %s, 0, %s, 'notas_credito', %s)""",
                (fecha, devoluciones["id"], descripcion, total, nota_id),
            )
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

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            user = cur.execute(
                "SELECT id, usuario, clave, rol, activo FROM usuarios WHERE usuario = %s",
                (usuario,),
            ).fetchone()
            conn.close()
        except Exception:
            user = None

        if user:
            try:
                if user["activo"] == 1 and check_password_hash(user["clave"], clave):
                    session["user"] = user["usuario"]
                    session["rol"] = user["rol"]
                    return redirect(url_for("facturacion"))
                else:
                    return render_template("login.html", error="Usuario o clave incorrectos")
            except Exception:
                if user["activo"] == 1 and user["clave"] == clave:
                    session["user"] = user["usuario"]
                    session["rol"] = user["rol"]
                    return redirect(url_for("facturacion"))
                return render_template("login.html", error="Usuario o clave incorrectos")

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
# FACTURACION
# =========================
@app.route("/facturacion")
def facturacion():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        clientes = cur.execute("SELECT id, nombres || ' ' || COALESCE(apellidos,'') as nombre FROM terceros WHERE tipo='Cliente'").fetchall()
    except Exception:
        clientes = []
    try:
        productos = cur.execute("SELECT id, nombre, precio, stock FROM productos").fetchall()
    except Exception:
        productos = []
    try:
        cur.execute("SELECT COALESCE(MAX(numero), 0) + 1 AS next_num FROM facturas")
        row = cur.fetchone()
        next_num = row["next_num"] if row else 1
    except Exception:
        next_num = 1
    conn.close()

    return render_template("facturacion.html",
                           user=session["user"],
                           clientes=clientes,
                           productos=productos,
                           factura_num=next_num,
                           fecha=datetime.now().strftime("%Y-%m-%d"))

@app.route("/facturacion/save", methods=["POST"])
def facturacion_save():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    try:
        data = request.get_json()
        cliente_id = data.get("cliente_id")
        numero = data.get("numero")
        fecha = data.get("fecha")
        lines = data.get("lines", [])

        total = sum(float(l["total"]) for l in lines)

        conn = get_db_connection()
        cur = conn.cursor()

        # Insertar factura con consecutivo
        cur.execute("""
            INSERT INTO facturas (tercero_id, numero, fecha, total)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (cliente_id, numero, fecha, total))
        row = cur.fetchone()

        # ✅ Detectar el nombre correcto de la PK
        if "id" in row:
            factura_id = row["id"]
        elif "factura_id" in row:
            factura_id = row["factura_id"]
        else:
            raise Exception("No se encontró la columna PK en facturas")

        # Detalle de factura y actualización de inventario
        for l in lines:
            cur.execute("""
                INSERT INTO detalle_factura (factura_id, producto_id, cantidad, precio, total)
                VALUES (%s, %s, %s, %s, %s)
            """, (factura_id, l["producto_id"], l["cantidad"], l["precio"], l["total"]))

            cur.execute("""
                UPDATE productos
                SET stock = stock - ?
                WHERE id = ?
            """.replace("?", "%s"), (l["cantidad"], l["producto_id"]))

        conn.commit()
        conn.close()

        return jsonify({"success": True, "factura_num": numero})
    except Exception as e:
        print("Error en facturacion_save:", e)
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
                   t.nombres || ' ' || COALESCE(t.apellidos,'') AS cliente
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
            WHERE f.id = %s
        """, (factura_id,)).fetchone()
        
        if not factura:
            conn.close()
            return redirect(url_for("facturas"))
        
        # Obtener tercero
        tercero = cur.execute("""
            SELECT nombres, apellidos, telefono, direccion
            FROM terceros WHERE id = %s
        """, (factura["tercero_id"],)).fetchone()
        
        # Obtener detalle
        detalle = cur.execute("""
            SELECT df.cantidad, df.precio, df.total, p.nombre AS producto
            FROM detalle_factura df 
            JOIN productos p ON df.producto_id = p.id
            WHERE df.factura_id = %s
        """, (factura_id,)).fetchall()
        
        # Obtener notas de crédito asociadas
        notas_credito = cur.execute("""
            SELECT nc.numero, nc.fecha, nc.total, nc.motivo
            FROM notas_credito nc
            WHERE nc.factura_id = %s
            ORDER BY nc.fecha DESC
        """, (factura_id,)).fetchall()
        
    except Exception:
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
            WHERE f.id = %s
        """, (factura_id,)).fetchone()
        
        if not factura:
            conn.close()
            return redirect(url_for("facturas"))
        
        # Obtener detalle de la factura
        detalle = cur.execute("""
            SELECT df.producto_id, df.cantidad, df.precio, p.nombre AS descripcion
            FROM detalle_factura df 
            JOIN productos p ON df.producto_id = p.id
            WHERE df.factura_id = %s
        """, (factura_id,)).fetchall()
        
        # Obtener próximo número de nota de crédito
        cur.execute("SELECT MAX(numero) AS max_num FROM notas_credito")
        row = cur.fetchone()
        last_num = row["max_num"] if row and row["max_num"] else 0
        next_num = last_num + 1
        
    except Exception:
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
        factura_info = cur.execute(
            "SELECT tercero_id FROM facturas WHERE id = %s", (factura_id,)
        ).fetchone()
        tercero_id = factura_info["tercero_id"] if factura_info else None
        
        # Insertar nota de crédito
        cur.execute("""
            INSERT INTO notas_credito (factura_id, numero, fecha, tercero_id, motivo, total, creado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (factura_id, numero, fecha, tercero_id, motivo, total_nota, session["user"]))
        
        nota_id = cur.fetchone()["id"]
        
        # Insertar detalle y devolver inventario
        for i in range(len(producto_ids)):
            cantidad = float(cantidades[i]) if cantidades[i] else 0
            if cantidad > 0:
                precio = float(precios[i])
                total_linea = float(totales_linea[i])
                
                cur.execute("""
                    INSERT INTO detalle_nota_credito 
                    (nota_id, producto_id, descripcion, cantidad, precio, total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (nota_id, producto_ids[i], descripciones[i], cantidad, precio, total_linea))
                
                cur.execute(
                    "UPDATE productos SET stock = stock + %s WHERE id = %s",
                    (cantidad, producto_ids[i]),
                )
        
        conn.commit()
        conn.close()
        
        crear_asiento_nota_credito(nota_id)
        
        return redirect(url_for("ver_factura", factura_id=factura_id))
        
    except Exception:
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
        proveedores = cur.execute("""
            SELECT id, nombres || ' ' || COALESCE(apellidos,'') AS nombre
            FROM terceros WHERE tipo='Proveedor'
        """).fetchall()
    except Exception:
        proveedores = []
    try:
        productos = cur.execute("SELECT id, nombre, stock, costo FROM productos").fetchall()
    except Exception:
        productos = []
    try:
        cur.execute("SELECT MAX(id) AS max_id FROM compras")
        row = cur.fetchone()
        last_num = row["max_id"] if row and row["max_id"] else 0
    except Exception:
        last_num = 0
    conn.close()

    return render_template(
        "compras.html",
        user=session["user"],
        proveedores=proveedores,
        productos=productos,
        compra_num=last_num + 1,
        fecha=datetime.now().strftime("%Y-%m-%d"),
    )


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
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (proveedor_id, numero, fecha, total, forma_pago, 1 if forma_pago == "contado" else 0))
        compra_id = cur.fetchone()["id"]

        # Detalle y actualización de inventario
        for l in lines:
            cur.execute("""
                INSERT INTO detalle_compra (compra_id, producto_id, cantidad, costo, total)
                VALUES (%s, %s, %s, %s, %s)
            """, (compra_id, l["producto_id"], l["cantidad"], l["costo"], l["total"]))

            cur.execute("""
                UPDATE productos
                SET stock = stock + %s, costo = %s
                WHERE id = %s
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
        productos_raw = cur.execute(
            "SELECT id, nombre, stock, costo, precio FROM productos"
        ).fetchall()
    except Exception:
        productos_raw = []
    conn.close()

    productos = [
        {
            "id": p["id"],
            "nombre": p["nombre"],
            "stock": p["stock"],
            "costo": p["costo"],
            "precio": p["precio"],
        }
        for p in productos_raw
    ]
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
        cur.execute(
            "INSERT INTO productos (nombre, stock, costo, precio) VALUES (%s, %s, %s, %s)",
            (nombre, stock, costo, precio),
        )
        conn.commit()
        # En PostgreSQL lastrowid no existe, usamos RETURNING
        cur.execute("SELECT currval(pg_get_serial_sequence('productos','id')) AS id;")
        nuevo_id = cur.fetchone()["id"]
        conn.close()
        return jsonify(
            {
                "success": True,
                "id": nuevo_id,
                "mensaje": f"Producto '{nombre}' agregado correctamente",
            }
        )
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
        cur.execute(
            "UPDATE productos SET nombre=%s, stock=%s, costo=%s, precio=%s WHERE id=%s",
            (nombre, stock, costo, precio, producto_id),
        )
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
        cur.execute("DELETE FROM productos WHERE id=%s", (producto_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "mensaje": "Producto eliminado correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =========================
# API / DEBUG: listar productos
# =========================
@app.route("/api/productos")
def api_productos():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        prows = cur.execute(
            "SELECT id, nombre, stock, costo, precio FROM productos ORDER BY nombre"
        ).fetchall()
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
        productos = [dict(p) for p in cur.execute(
            "SELECT id, nombre, stock, costo, precio FROM productos ORDER BY nombre"
        ).fetchall()]
        transformaciones = [dict(t) for t in cur.execute("""
            SELECT id, numero, fecha, descripcion, total_salida, total_entrada, creado_por
            FROM transformaciones
            ORDER BY fecha DESC, id DESC
        """).fetchall()]
    except Exception as e:
        print("Error cargando transformaciones:", e)
        productos, transformaciones = [], []
    finally:
        conn.close()

    return render_template("transformaciones.html",
                           user=session["user"],
                           productos=productos,
                           transformaciones=transformaciones,
                           fecha_hoy=datetime.now().strftime("%Y-%m-%d"))


@app.route("/transformaciones/save", methods=["POST"])
def save_transformacion():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401

    try:
        data = request.get_json() or {}
        fecha = data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
        descripcion = data.get("descripcion", "")
        salidas = data.get("salidas", [])
        entradas = data.get("entradas", [])

        total_salida = 0.0
        total_entrada = 0.0

        conn = get_db_connection()
        cur = conn.cursor()

        # ✅ Consecutivo automático
        cur.execute("SELECT COALESCE(MAX(numero), 0) + 1 AS next_num FROM transformaciones")
        numero = cur.fetchone()["next_num"]

        # Insertar cabecera
        cur.execute("""
            INSERT INTO transformaciones (numero, fecha, descripcion, total_salida, total_entrada, creado_por)
            VALUES (%s, %s, %s, 0, 0, %s) RETURNING id
        """, (numero, fecha, descripcion, session["user"]))
        trans_id = cur.fetchone()["id"]

        # Registrar salidas
        for s in salidas:
            pid = int(s.get("producto_id"))
            cant = float(s.get("cantidad") or 0)
            if cant <= 0:
                continue
            prod = cur.execute("SELECT costo FROM productos WHERE id=%s", (pid,)).fetchone()
            costo_unit = float(prod["costo"]) if prod else 0.0
            total = cant * costo_unit
            total_salida += total

            cur.execute("""
                INSERT INTO detalle_transformacion (transformacion_id, tipo, producto_id, cantidad, costo, total)
                VALUES (%s, 'salida', %s, %s, %s, %s)
            """, (trans_id, pid, cant, costo_unit, total))
            cur.execute("UPDATE productos SET stock = stock - %s WHERE id=%s", (cant, pid))

        # Registrar entradas
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
                VALUES (%s, 'entrada', %s, %s, %s, %s)
            """, (trans_id, pid, cant, costo_unit, total))
            cur.execute("UPDATE productos SET stock = stock + %s, costo = %s WHERE id=%s", (cant, costo_unit, pid))

        # Actualizar totales
        cur.execute("UPDATE transformaciones SET total_salida=%s, total_entrada=%s WHERE id=%s",
                    (total_salida, total_entrada, trans_id))

        conn.commit()
        conn.close()

        # Asiento contable
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            inventario = cur.execute("SELECT id FROM puc WHERE codigo='1435'").fetchone()
            if inventario:
                cur.execute("""
                    INSERT INTO movimientos_contables (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                    VALUES (%s, %s, %s, %s, 0, 'transformacion', %s)
                """, (fecha, inventario["id"], f"Transformación {numero}", total_entrada, trans_id))
                cur.execute("""
                    INSERT INTO movimientos_contables (fecha, cuenta_id, descripcion, debito, credito, modulo, referencia_id)
                    VALUES (%s, %s, %s, 0, %s, 'transformacion', %s)
                """, (fecha, inventario["id"], f"Transformación {numero}", total_salida, trans_id))
                conn.commit()
        except Exception as e:
            print("Error asiento transformación:", e)
        finally:
            conn.close()

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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO terceros (nombres, apellidos, telefono, correo, direccion, tipo) 
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (data.get("nombres"), data.get("apellidos"), data.get("telefono"),
              data.get("correo"), data.get("direccion"), data.get("tipo")))
        tercero_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": tercero_id, "nombre": f"{data.get('nombres')} {data.get('apellidos')}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================
# GASTOS
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
        terceros = cur.execute("SELECT id, nombres || ' ' || COALESCE(apellidos,'') AS nombre FROM terceros").fetchall()
    except Exception:
        terceros = []
    try:
        cur.execute("SELECT MAX(numero) AS max_num FROM recibos_caja")
        row = cur.fetchone()
        last_num = row["max_num"] if row and row["max_num"] else 0
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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO recibos_caja (numero, fecha, tercero_id, concepto, valor) 
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (data.get("numero"), data.get("fecha") or datetime.now().strftime("%Y-%m-%d"),
              data.get("tercero_id"), data.get("concepto"), float(data.get("valor"))))
        recibo_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        crear_asiento_recibo(recibo_id)
        return jsonify({"success": True, "recibo_num": data.get("numero")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/recibos/lista", methods=["POST"])
def api_recibos_lista():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        recibos = cur.execute("""
            SELECT r.id, r.numero, r.fecha, r.concepto, r.valor,
                   t.nombres || ' ' || COALESCE(t.apellidos,'') AS tercero
            FROM recibos_caja r
            LEFT JOIN terceros t ON r.tercero_id = t.id
            WHERE r.fecha BETWEEN %s AND %s
            ORDER BY r.fecha DESC, r.numero DESC
        """, (data.get("fecha_inicio"), data.get("fecha_fin"))).fetchall()
        conn.close()
        return jsonify({"success": True, "recibos": [dict(r) for r in recibos]})
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
        terceros = cur.execute("SELECT id, nombres || ' ' || COALESCE(apellidos,'') AS nombre FROM terceros").fetchall()
    except Exception:
        terceros = []
    try:
        cur.execute("SELECT MAX(numero) AS max_num FROM comprobantes_egreso")
        row = cur.fetchone()
        last_num = row["max_num"] if row and row["max_num"] else 0
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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO comprobantes_egreso (numero, fecha, tercero_id, concepto, valor)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (data.get("numero"), data.get("fecha") or datetime.now().strftime("%Y-%m-%d"),
              data.get("tercero_id"), data.get("concepto"), float(data.get("valor"))))
        egreso_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        crear_asiento_egreso(egreso_id)
        return jsonify({"success": True, "egreso_num": data.get("numero")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/egresos/lista", methods=["POST"])
def api_egresos_lista():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        egresos = cur.execute("""
            SELECT e.id, e.numero, e.fecha, e.concepto, e.valor,
                   t.nombres || ' ' || COALESCE(t.apellidos,'') AS tercero
            FROM comprobantes_egreso e
            LEFT JOIN terceros t ON e.tercero_id = t.id
            WHERE e.fecha BETWEEN %s AND %s
            ORDER BY e.fecha DESC, e.numero DESC
        """, (data.get("fecha_inicio"), data.get("fecha_fin"))).fetchall()
        conn.close()
        return jsonify({"success": True, "egresos": [dict(e) for e in egresos]})
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
    conn = get_db_connection(); cur = conn.cursor()
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
    return render_template("movimientos.html", user=session["user"],
                           fecha_inicio=first_day_month, fecha_fin=today)


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
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO puc (codigo, nombre, tipo) VALUES (%s, %s, %s)",
                    (codigo, nombre, tipo))
        conn.commit(); conn.close()
        return jsonify({"success": True, "mensaje": f"Cuenta {codigo} agregada correctamente"})
    except Exception as e:
        # Error por duplicado en clave primaria/única
        if "duplicate key" in str(e).lower():
            return jsonify({"success": False, "error": "El código de cuenta ya existe"})
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/movimientos", methods=["POST"])
def get_movimientos():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fecha_inicio, fecha_fin = data.get("fecha_inicio"), data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        movimientos = cur.execute("""
            SELECT m.fecha, m.descripcion, p.codigo, p.nombre, 
                   m.debito, m.credito, m.modulo, m.referencia_id
            FROM movimientos_contables m
            JOIN puc p ON m.cuenta_id = p.id
            WHERE m.fecha BETWEEN %s AND %s
            ORDER BY m.fecha DESC, m.id DESC
        """, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        return jsonify({"success": True, "movimientos": [dict(r) for r in movimientos]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/balance", methods=["POST"])
def get_balance():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json(); fecha_fin = data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        balance = cur.execute("""
            SELECT p.codigo, p.nombre, p.tipo,
                   SUM(m.debito) AS total_debito,
                   SUM(m.credito) AS total_credito,
                   CASE WHEN p.tipo IN ('activo','gasto') 
                        THEN SUM(m.debito) - SUM(m.credito)
                        ELSE SUM(m.credito) - SUM(m.debito) END AS saldo
            FROM puc p
            LEFT JOIN movimientos_contables m 
                   ON p.id = m.cuenta_id AND m.fecha <= %s
            GROUP BY p.id, p.codigo, p.nombre, p.tipo
            HAVING SUM(COALESCE(m.debito,0)) > 0 OR SUM(COALESCE(m.credito,0)) > 0
            ORDER BY p.codigo
        """, (fecha_fin,)).fetchall()
        conn.close()
        return jsonify({"success": True, "balance": [dict(r) for r in balance]})
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
        conn = get_db_connection(); cur = conn.cursor()
        for codigo, nombre, tipo in cuentas_basicas:
            cur.execute("""
                INSERT INTO puc (codigo, nombre, tipo) 
                VALUES (%s, %s, %s)
                ON CONFLICT (codigo) DO NOTHING
            """, (codigo, nombre, tipo))
        conn.commit(); conn.close()
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
    return render_template("resumenes.html", user=session["user"],
                           fecha_inicio=first_day_month, fecha_fin=today)


@app.route("/api/resumen/ventas", methods=["POST"])
def api_resumen_ventas():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json()
    fi, ff = data.get("fecha_inicio"), data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        ventas_diarias = cur.execute("""
            SELECT DATE(fecha) AS dia, COUNT(*) AS num_facturas, SUM(total) AS total_ventas
            FROM facturas WHERE fecha BETWEEN %s AND %s
            GROUP BY DATE(fecha) ORDER BY dia
        """, (fi, ff)).fetchall()
        total_periodo = cur.execute("""
            SELECT COUNT(*) AS facturas, SUM(total) AS total, AVG(total) AS promedio
            FROM facturas WHERE fecha BETWEEN %s AND %s
        """, (fi, ff)).fetchone()
        producto_top = cur.execute("""
            SELECT p.nombre, SUM(df.cantidad) AS cantidad_vendida, SUM(df.total) AS ingresos_producto
            FROM detalle_factura df 
            JOIN productos p ON df.producto_id = p.id
            JOIN facturas f ON df.factura_id = f.id
            WHERE f.fecha BETWEEN %s AND %s
            GROUP BY p.id, p.nombre 
            ORDER BY cantidad_vendida DESC LIMIT 1
        """, (fi, ff)).fetchone()
        top_productos = cur.execute("""
            SELECT p.nombre, SUM(df.cantidad) AS cantidad_vendida, SUM(df.total) AS ingresos_producto,
                   COUNT(DISTINCT f.id) AS facturas_aparece
            FROM detalle_factura df 
            JOIN productos p ON df.producto_id = p.id 
            JOIN facturas f ON df.factura_id = f.id
            WHERE f.fecha BETWEEN %s AND %s
            GROUP BY p.id, p.nombre 
            ORDER BY cantidad_vendida DESC LIMIT 5
        """, (fi, ff)).fetchall()
        cliente_top = cur.execute("""
            SELECT t.nombres || ' ' || COALESCE(t.apellidos,'') AS cliente,
                   COUNT(*) AS num_compras, SUM(f.total) AS total_comprado
            FROM facturas f JOIN terceros t ON f.tercero_id = t.id
            WHERE f.fecha BETWEEN %s AND %s
            GROUP BY t.id, cliente ORDER BY total_comprado DESC LIMIT 1
        """, (fi, ff)).fetchone()
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
    fi, ff = data.get("fecha_inicio"), data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        compras_diarias = cur.execute("""
            SELECT DATE(fecha) AS dia, COUNT(*) AS num_compras, SUM(total) AS total_compras
            FROM compras WHERE fecha BETWEEN %s AND %s
            GROUP BY DATE(fecha) ORDER BY dia
        """, (fi, ff)).fetchall()
        total_compras = cur.execute("""
            SELECT COUNT(*) AS compras, SUM(total) AS total, AVG(total) AS promedio,
                   SUM(CASE WHEN pagada=1 THEN total ELSE 0 END) AS pagadas,
                   SUM(CASE WHEN pagada=0 THEN total ELSE 0 END) AS pendientes
            FROM compras WHERE fecha BETWEEN %s AND %s
        """, (fi, ff)).fetchone()
        proveedor_top = cur.execute("""
            SELECT t.nombres || ' ' || COALESCE(t.apellidos,'') AS proveedor,
                   COUNT(*) AS num_compras, SUM(c.total) AS total_comprado
            FROM compras c JOIN terceros t ON c.tercero_id = t.id
            WHERE c.fecha BETWEEN %s AND %s
            GROUP BY t.id, proveedor ORDER BY total_comprado DESC LIMIT 1
        """, (fi, ff)).fetchone()
        productos_comprados = cur.execute("""
            SELECT p.nombre, SUM(dc.cantidad) AS cantidad_comprada, SUM(dc.total) AS total_invertido,
                   COUNT(DISTINCT c.id) AS compras_aparece
            FROM detalle_compra dc 
            JOIN productos p ON dc.producto_id = p.id 
            JOIN compras c ON dc.compra_id = c.id
            WHERE c.fecha BETWEEN %s AND %s
            GROUP BY p.id, p.nombre ORDER BY cantidad_comprada DESC LIMIT 5
        """, (fi, ff)).fetchall()
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
    data = request.get_json(); fi, ff = data.get("fecha_inicio"), data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        facturas = cur.execute("""
            SELECT f.id, f.numero, f.fecha, f.total,
                   t.nombres || ' ' || COALESCE(t.apellidos,'') AS cliente
            FROM facturas f LEFT JOIN terceros t ON f.tercero_id = t.id
            WHERE f.fecha BETWEEN %s AND %s
            ORDER BY f.fecha DESC, f.numero DESC
        """, (fi, ff)).fetchall()
        conn.close()
        return jsonify({"success": True, "facturas": [dict(r) for r in facturas]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/compras/lista", methods=["POST"])
def api_compras_lista():
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    data = request.get_json(); fi, ff = data.get("fecha_inicio"), data.get("fecha_fin")
    try:
        conn = get_db_connection(); cur = conn.cursor()
        compras = cur.execute("""
            SELECT c.id, c.numero, c.fecha, c.total, c.forma_pago, c.pagada,
                   t.nombres || ' ' || COALESCE(t.apellidos,'') AS proveedor
            FROM compras c LEFT JOIN terceros t ON c.tercero_id = t.id
            WHERE c.fecha BETWEEN %s AND %s
            ORDER BY c.fecha DESC, c.numero DESC
        """, (fi, ff)).fetchall()
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
            SELECT f.*, t.nombres || ' ' || COALESCE(t.apellidos,'') AS cliente,
                   t.telefono, t.direccion
            FROM facturas f LEFT JOIN terceros t ON f.tercero_id = t.id
            WHERE f.id = %s
        """, (factura_id,)).fetchone()
        if not factura:
            conn.close()
            return jsonify({"success": False, "error": "Factura no encontrada"})
        detalle = cur.execute("""
            SELECT df.cantidad, df.precio, df.total, p.nombre AS producto
            FROM detalle_factura df JOIN productos p ON df.producto_id = p.id
            WHERE df.factura_id = %s
        """, (factura_id,)).fetchall()
        conn.close()
        return jsonify({"success": True,
                        "factura": dict(factura),
                        "detalle": [dict(r) for r in detalle]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/compra/<int:compra_id>")
def api_compra_detalle(compra_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    try:
        conn = get_db_connection(); cur = conn.cursor()
        compra = cur.execute("""
            SELECT c.*, t.nombres || ' ' || COALESCE(t.apellidos,'') AS proveedor,
                   t.telefono, t.direccion
            FROM compras c LEFT JOIN terceros t ON c.tercero_id = t.id
            WHERE c.id = %s
        """, (compra_id,)).fetchone()
        if not compra:
            conn.close()
            return jsonify({"success": False, "error": "Compra no encontrada"})
        detalle = cur.execute("""
            SELECT dc.cantidad, dc.costo, dc.total, p.nombre AS producto
            FROM detalle_compra dc JOIN productos p ON dc.producto_id = p.id
            WHERE dc.compra_id = %s
        """, (compra_id,)).fetchall()
        conn.close()
        return jsonify({"success": True,
                        "compra": dict(compra),
                        "detalle": [dict(r) for r in detalle]})
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
        usuarios = cur.execute(
            "SELECT id, usuario, rol, activo FROM usuarios ORDER BY id"
        ).fetchall()
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
        cur.execute(
            "INSERT INTO usuarios (usuario, clave, rol, activo) VALUES (%s, %s, %s, 1)",
            (usuario, hashed, rol),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "mensaje": "Usuario creado"})
    except Exception as e:
        if "duplicate key" in str(e).lower():
            return jsonify({"success": False, "error": "El usuario ya existe"})
        return jsonify({"success": False, "error": str(e)})


@app.route("/ajustes/usuarios/toggle/<int:user_id>", methods=["POST"])
def toggle_usuario(user_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "No autorizado"})
    try:
        conn = get_db_connection(); cur = conn.cursor()
        u = cur.execute("SELECT activo FROM usuarios WHERE id=%s", (user_id,)).fetchone()
        if not u:
            conn.close()
            return jsonify({"success": False, "error": "Usuario no encontrado"})
        nuevo_estado = 0 if u["activo"] == 1 else 1
        cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (nuevo_estado, user_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "estado": nuevo_estado})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/schema")
def schema():
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT table_name, ordinal_position, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()

    salida = {}
    for r in rows:
        tabla = r["table_name"]
        if tabla not in salida:
            salida[tabla] = []
        salida[tabla].append(f'{r["ordinal_position"]}. {r["column_name"]} ({r["data_type"]})')

    html = ""
    for tabla, cols in salida.items():
        html += f"<h3>Tabla: {tabla}</h3><ul>"
        for c in cols:
            html += f"<li>{c}</li>"
        html += "</ul>"
    return html


# =========================
# INICIO
# =========================
@app.route("/")
def index():
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
