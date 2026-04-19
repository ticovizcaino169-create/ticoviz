"""
TicoViz Corporation v2 — Auto Processor
Procesa pedidos automaticamente sin intervencion manual.
Flujo: Recibido -> IA crea producto -> Precio automatico -> Listo -> Notifica por Telegram.
Solo necesitas confirmar pagos manualmente (5 segundos desde Telegram).
"""
import logging
import asyncio
import threading
import time
import sqlite3
import requests
from datetime import datetime

import database as db
import orchestrator
from config import (
    TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_ID,
    DATABASE_PATH,
)

logger = logging.getLogger("ticoviz.auto")

POLL_INTERVAL = 60  # Revisar cada 60 segundos


# ==================== TELEGRAM NOTIFICATIONS ====================

def _send_telegram(text):
    """Envia notificacion al admin via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_USER_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": AUTHORIZED_USER_ID,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        logger.error(f"Error sending Telegram: {e}")


# ==================== DATABASE HELPERS ====================

def _get_pending_orders():
    """Obtiene pedidos con status 'recibido'."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM web_orders WHERE order_status = 'recibido' "
            "ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def _get_payment_pending_orders():
    """Obtiene pedidos donde el cliente dice que pago."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM web_orders WHERE payment_status = 'esperando_confirmacion' "
            "ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def _update_order(order_id, **kwargs):
    """Actualiza campos de un pedido."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    try:
        sets = ", ".join(f"{k} = ?" for k in kwargs.keys())
        vals = list(kwargs.values())
        vals.append(datetime.now().isoformat())
        vals.append(order_id)
        conn.execute(
            f"UPDATE web_orders SET {sets}, updated_at = ? WHERE id = ?",
            vals,
        )
        conn.commit()
    finally:
        conn.close()


def _get_product_price(product_id):
    """Obtiene precio sugerido del producto creado."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT precio_sugerido FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row:
            return float(row["precio_sugerido"])
        return 0.0
    except Exception:
        return 0.0
    finally:
        conn.close()


# ==================== AUTO PROCESSING ====================

async def _process_order(order):
    """Procesa un pedido automaticamente con NV8."""
    order_id = order["id"]
    descripcion = order["descripcion"]
    cliente = order.get("cliente_nombre", "N/A")
    contacto = order.get("cliente_contacto", "N/A")

    logger.info(f"Auto-processing order #{order_id}")

    _send_telegram(
        f"<b>Auto-procesando pedido #{order_id}</b>\n"
        f"Cliente: {cliente}\n"
        f"Contacto: {contacto}\n"
        f"Descripcion: {descripcion[:300]}\n\n"
        f"Los motores de IA estan trabajando..."
    )

    # Cambiar status a procesando
    _update_order(order_id, order_status="procesando")

    try:
        # Ejecutar pipeline completo NV8
        resultado = await orchestrator.flujo_crear_producto(descripcion)

        if resultado.get("status") == "error":
            error_msg = resultado.get("error", "Error desconocido")
            _send_telegram(
                f"Error procesando #{order_id}: {error_msg}\n"
                f"El pedido vuelve a 'recibido'. Puedes procesarlo manual con "
                f"/web_procesar {order_id}"
            )
            _update_order(order_id, order_status="recibido")
            return

        # Obtener product_id y precio
        product_id = resultado.get("product_id", 0)
        precio = 0.0

        # Intentar obtener precio del producto creado
        if product_id:
            precio = _get_product_price(product_id)

        # Si la IA no sugiere precio, calcular basado en categoria
        if precio <= 0:
            categoria = order.get("categoria", "otro")
            precios_base = {
                "app": 50.0, "bot": 35.0, "herramienta": 25.0,
                "juego": 45.0, "api": 40.0, "template": 20.0,
                "saas": 75.0, "otro": 30.0,
            }
            precio = precios_base.get(categoria, 30.0)

        # Minimo $10, maximo $500
        precio = max(10.0, min(precio, 500.0))

        # Actualizar pedido: listo con precio y producto
        _update_order(
            order_id,
            order_status="listo",
            product_id=product_id,
            precio=precio,
        )

        motores = ", ".join(resultado.get("motores_usados", ["NV8"]))
        tokens = resultado.get("tokens_total", 0)

        _send_telegram(
            f"<b>Pedido #{order_id} LISTO</b>\n"
            f"{'=' * 30}\n"
            f"Cliente: {cliente}\n"
            f"Producto: #{product_id}\n"
            f"Precio: ${precio:.2f} USD\n"
            f"Motores: {motores}\n"
            f"Tokens: {tokens:,}\n\n"
            f"El cliente ya puede pagar desde la web.\n"
            f"Cuando pague, te llega notificacion para confirmar."
        )

        logger.info(
            f"Order #{order_id} completed: product #{product_id}, "
            f"price ${precio:.2f}"
        )

    except Exception as e:
        logger.error(f"Error auto-processing order #{order_id}: {e}")
        _send_telegram(
            f"Error auto-procesando #{order_id}: {str(e)[:300]}\n"
            f"El pedido vuelve a 'recibido'."
        )
        _update_order(order_id, order_status="recibido")


def _check_payment_notifications():
    """Revisa si hay pagos pendientes de confirmar y notifica."""
    orders = _get_payment_pending_orders()
    for order in orders:
        order_id = order["id"]
        tx_hash = order.get("tx_hash", "")
        crypto = order.get("crypto_tipo", "")
        precio = order.get("precio", 0) or 0

        _send_telegram(
            f"<b>PAGO PENDIENTE #{order_id}</b>\n"
            f"{'=' * 30}\n"
            f"Cliente: {order.get('cliente_nombre', 'N/A')}\n"
            f"Monto: ${precio:.2f}\n"
            f"Crypto: {crypto}\n"
            f"TX Hash: <code>{tx_hash}</code>\n\n"
            f"Para confirmar:\n"
            f"/web_confirmar_pago {order_id}\n\n"
            f"Para rechazar:\n"
            f"/web_rechazar_pago {order_id}"
        )


# ==================== WORKER LOOP ====================

def _worker_loop():
    """Loop principal del worker. Corre en background."""
    logger.info("Auto-processor started. Polling every 60s.")
    _send_telegram(
        "<b>Auto-processor iniciado</b>\n"
        "Los pedidos se procesaran automaticamente.\n"
        "Solo necesitas confirmar pagos cuando lleguen."
    )

    while True:
        try:
            # 1. Procesar pedidos nuevos
            orders = _get_pending_orders()
            if orders:
                logger.info(f"Found {len(orders)} pending orders")
                for order in orders:
                    try:
                        asyncio.run(_process_order(order))
                    except Exception as e:
                        logger.error(f"Error processing order: {e}")
                    time.sleep(5)  # Pausa entre pedidos

            # 2. Revisar pagos pendientes
            _check_payment_notifications()

        except Exception as e:
            logger.error(f"Auto-processor error: {e}")

        time.sleep(POLL_INTERVAL)


def start_auto_processor():
    """Inicia el auto-processor en un thread daemon."""
    thread = threading.Thread(
        target=_worker_loop,
        daemon=True,
        name="auto-processor",
    )
    thread.start()
    logger.info("Auto-processor thread launched")
    return thread
