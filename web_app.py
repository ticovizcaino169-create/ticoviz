"""
TicoViz Corporation v2 — Portal Web para Clientes
Clientes hacen pedidos -> Sistema genera -> Pago crypto -> Entrega.
"""
import os
import uuid
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, send_file, jsonify, flash, abort,
)
import requests as http_requests

from config import (
    TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_ID,
    PRODUCTS_DIR, DATABASE_PATH, WEB_SECRET_KEY,
    WEB_PORT, WEB_HOST, CATEGORIAS,
)
from payment import generar_info_pago, get_cryptos_disponibles

logger = logging.getLogger("ticoviz.web")


# ==================== BASE DE DATOS WEB ====================

def _get_web_conn():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_orders_db():
    """Crea tabla web_orders si no existe."""
    conn = _get_web_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS web_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                cliente_nombre TEXT NOT NULL,
                cliente_contacto TEXT NOT NULL,
                categoria TEXT DEFAULT 'otro',
                descripcion TEXT NOT NULL,
                notas TEXT DEFAULT '',
                order_status TEXT DEFAULT 'recibido',
                payment_status TEXT DEFAULT 'pendiente',
                precio REAL DEFAULT 0.0,
                crypto_tipo TEXT DEFAULT '',
                tx_hash TEXT DEFAULT '',
                product_id INTEGER DEFAULT 0,
                archivos_json TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _crear_order(token, nombre, contacto, categoria, descripcion, notas):
    conn = _get_web_conn()
    try:
        cur = conn.execute(
            "INSERT INTO web_orders (token, cliente_nombre, cliente_contacto, "
            "categoria, descripcion, notas) VALUES (?, ?, ?, ?, ?, ?)",
            (token, nombre, contacto, categoria, descripcion, notas),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _get_order_by_token(token):
    conn = _get_web_conn()
    try:
        row = conn.execute(
            "SELECT * FROM web_orders WHERE token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_order_by_id(order_id):
    conn = _get_web_conn()
    try:
        row = conn.execute(
            "SELECT * FROM web_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _update_order(order_id, **kwargs):
    conn = _get_web_conn()
    try:
        sets = ", ".join(f"{k} = ?" for k in kwargs.keys())
        vals = list(kwargs.values()) + [order_id]
        conn.execute(
            f"UPDATE web_orders SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            vals,
        )
        conn.commit()
    finally:
        conn.close()


def _notificar_telegram(mensaje):
    """Envia notificacion a David via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_USER_ID:
        logger.warning("Telegram no configurado para notificaciones")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        http_requests.post(url, json={
            "chat_id": AUTHORIZED_USER_ID,
            "text": mensaje,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        logger.error(f"Error enviando notificacion Telegram: {e}")


def _get_public_stats():
    """Stats basicas para la landing page."""
    conn = _get_web_conn()
    try:
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM web_orders WHERE order_status = 'entregado'"
            ).fetchone()[0]
        except Exception:
            total = 0
        return {"productos_entregados": total}
    finally:
        conn.close()


# ==================== FLASK APP ====================

def create_app():
    """Factory de la aplicacion Flask."""
    app = Flask(__name__)
    app.secret_key = WEB_SECRET_KEY

    _init_orders_db()

    # ==================== RUTAS PUBLICAS ====================

    @app.route("/")
    def index():
        stats = _get_public_stats()
        return render_template("index.html", stats=stats)

    @app.route("/servicios")
    def servicios():
        return render_template("index.html", stats=_get_public_stats())

    @app.route("/pedir", methods=["GET"])
    def pedir_form():
        return render_template("pedir.html", categorias=CATEGORIAS)

    @app.route("/pedir", methods=["POST"])
    def pedir_submit():
        nombre = request.form.get("nombre", "").strip()
        contacto = request.form.get("contacto", "").strip()
        categoria = request.form.get("categoria", "otro")
        descripcion = request.form.get("descripcion", "").strip()
        notas = request.form.get("notas", "").strip()

        errores = []
        if not nombre:
            errores.append("El nombre es obligatorio")
        if not contacto:
            errores.append("El contacto es obligatorio")
        if not descripcion or len(descripcion) < 10:
            errores.append("La descripcion debe tener al menos 10 caracteres")
        if len(descripcion) > 2000:
            errores.append("La descripcion no puede superar 2000 caracteres")

        if errores:
            return render_template(
                "pedir.html", categorias=CATEGORIAS,
                errores=errores, form=request.form,
            )

        token = uuid.uuid4().hex[:16]
        order_id = _crear_order(token, nombre, contacto, categoria, descripcion, notas)

        _notificar_telegram(
            f"<b>Nuevo pedido #{order_id}</b>\n\n"
            f"Cliente: {nombre}\n"
            f"Contacto: {contacto}\n"
            f"Categoria: {categoria}\n"
            f"Descripcion:\n{descripcion[:300]}\n\n"
            f"Token: <code>{token}</code>\n\n"
            f"Usa /web_pedido {order_id} para ver detalles\n"
            f"Usa /web_procesar {order_id} para generar el producto\n"
            f"Usa /web_precio {order_id} MONTO para fijar precio"
        )

        return redirect(url_for("ver_pedido", token=token))

    @app.route("/pedido/<token>")
    def ver_pedido(token):
        order = _get_order_by_token(token)
        if not order:
            abort(404)
        return render_template("estado.html", order=order)

    @app.route("/pedido/<token>/pagar")
    def pagar(token):
        order = _get_order_by_token(token)
        if not order:
            abort(404)
        if order["order_status"] != "listo":
            flash("El pedido aun no esta listo para pagar.")
            return redirect(url_for("ver_pedido", token=token))
        if order["precio"] <= 0:
            flash("El precio aun no ha sido fijado.")
            return redirect(url_for("ver_pedido", token=token))

        crypto_actual = request.args.get("crypto", "USDT_TRC20")
        cryptos = get_cryptos_disponibles()
        pago_info = generar_info_pago(order["precio"], crypto_actual)

        return render_template(
            "pagar.html", order=order, pago=pago_info,
            cryptos=cryptos, crypto_actual=crypto_actual,
        )

    @app.route("/pedido/<token>/confirmar_pago", methods=["POST"])
    def confirmar_pago(token):
        order = _get_order_by_token(token)
        if not order:
            abort(404)

        tx_hash = request.form.get("tx_hash", "").strip()
        crypto_tipo = request.form.get("crypto_tipo", "USDT_TRC20")

        if not tx_hash:
            flash("Debes ingresar el hash de la transaccion.")
            return redirect(url_for("pagar", token=token))

        _update_order(
            order["id"],
            payment_status="esperando_confirmacion",
            tx_hash=tx_hash,
            crypto_tipo=crypto_tipo,
        )

        _notificar_telegram(
            f"<b>Pago reportado — Pedido #{order['id']}</b>\n\n"
            f"Cliente: {order['cliente_nombre']}\n"
            f"Crypto: {crypto_tipo}\n"
            f"TX Hash: <code>{tx_hash}</code>\n"
            f"Monto: ${order['precio']:.2f}\n\n"
            f"Usa /web_confirmar {order['id']} para confirmar el pago"
        )

        return render_template("pago_enviado.html", order=order)

    @app.route("/pedido/<token>/descargar")
    def descargar_page(token):
        order = _get_order_by_token(token)
        if not order:
            abort(404)
        if order["payment_status"] != "pagado":
            flash("El pago aun no ha sido confirmado.")
            return redirect(url_for("ver_pedido", token=token))

        archivos = json.loads(order.get("archivos_json", "[]"))
        return render_template("descargar.html", order=order, archivos=archivos)

    @app.route("/pedido/<token>/descargar/<filename>")
    def descargar_archivo(token, filename):
        order = _get_order_by_token(token)
        if not order:
            abort(404)
        if order["payment_status"] != "pagado":
            abort(403)

        archivos = json.loads(order.get("archivos_json", "[]"))
        if filename not in archivos:
            abort(404)

        # Buscar archivo en directorio del producto
        product_id = order.get("product_id", 0)
        if product_id:
            filepath = PRODUCTS_DIR / f"product_{product_id}" / filename
        else:
            filepath = PRODUCTS_DIR / filename

        if not filepath.exists():
            abort(404)

        return send_file(str(filepath), as_attachment=True, download_name=filename)

    # ==================== ERROR HANDLERS ====================

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, msg="Pagina no encontrada"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, msg="Acceso denegado"), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", code=500, msg="Error interno del servidor"), 500

    return app


# ==================== FUNCIONES EXPORTADAS PARA BOT ====================

def web_listar_pedidos(limit: int = 10) -> list:
    """Lista pedidos web recientes."""
    conn = _get_web_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM web_orders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def web_ver_pedido(order_id: int) -> dict:
    """Ver detalle de un pedido."""
    return _get_order_by_id(order_id)


def web_procesar_pedido(order_id: int) -> bool:
    """Marca pedido como procesando."""
    order = _get_order_by_id(order_id)
    if not order:
        return False
    _update_order(order_id, order_status="procesando")
    return True


def web_set_precio(order_id: int, precio: float) -> bool:
    """Fija el precio de un pedido."""
    order = _get_order_by_id(order_id)
    if not order:
        return False
    _update_order(order_id, precio=precio, order_status="listo")
    return True


def web_confirmar_pago(order_id: int) -> bool:
    """Confirma pago y habilita descarga."""
    order = _get_order_by_id(order_id)
    if not order:
        return False
    _update_order(order_id, payment_status="pagado", order_status="entregado")
    return True


def web_cancelar_pedido(order_id: int) -> bool:
    """Cancela un pedido."""
    order = _get_order_by_id(order_id)
    if not order:
        return False
    _update_order(order_id, order_status="cancelado")
    return True


def web_set_archivos(order_id: int, archivos: list, product_id: int = 0) -> bool:
    """Asigna archivos a un pedido."""
    order = _get_order_by_id(order_id)
    if not order:
        return False
    _update_order(
        order_id,
        archivos_json=json.dumps(archivos),
        product_id=product_id,
    )
    return True


def run_web():
    """Ejecuta el servidor Flask."""
    app = create_app()
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)
