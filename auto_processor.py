"""
TicoViz Corporation v2 — Auto Processor
Procesa automaticamente pedidos web nuevos cuando llegan.
Se ejecuta en un thread separado, polling cada 30 segundos.
"""

import logging
import asyncio
import threading
import time
from datetime import datetime

logger = logging.getLogger("ticoviz.auto_processor")


def start_auto_processor():
    """
    Lanza el auto-processor en un thread daemon.
    Monitorea pedidos con status 'recibido' y los procesa automaticamente.
    """
    thread = threading.Thread(target=_auto_processor_loop, daemon=True)
    thread.start()
    logger.info("Auto-processor iniciado (polling cada 30s)")


def _auto_processor_loop():
    """Loop principal del auto-processor."""
    # Esperar a que la app arranque completamente
    time.sleep(10)
    logger.info("Auto-processor activo — monitoreando pedidos nuevos")

    while True:
        try:
            _check_and_process()
        except Exception as e:
            logger.error(f"Auto-processor error en ciclo: {e}", exc_info=True)

        time.sleep(30)


def _check_and_process():
    """Verifica si hay pedidos pendientes y los procesa."""
    try:
        import web_app
        import orchestrator
    except ImportError as e:
        logger.error(f"Auto-processor: import error: {e}")
        return

    # Obtener pedidos con status 'recibido'
    pedidos = web_app.web_listar_pedidos(50)
    if not pedidos:
        return

    pendientes = [p for p in pedidos if p.get("order_status") == "recibido"]

    if not pendientes:
        return

    for pedido in pendientes:
        order_id = pedido.get("id")
        descripcion = pedido.get("descripcion", "")
        cliente = pedido.get("cliente_nombre", "desconocido")

        if not descripcion or not descripcion.strip():
            logger.warning(f"Auto-processor: Pedido #{order_id} sin descripcion, saltando")
            continue

        logger.info(f"Auto-procesando pedido #{order_id} de {cliente}")

        try:
            # Marcar como procesando
            web_app.web_procesar_pedido(order_id)

            # Crear event loop para correr async
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Callback para logging (no hay chat de Telegram en auto-mode)
                async def log_notify(msg):
                    logger.info(f"[Auto #{order_id}] {msg}")

                # Notificar por Telegram si es posible
                notify_func = _get_telegram_notify(order_id, cliente, descripcion)

                resultado = loop.run_until_complete(
                    orchestrator.flujo_crear_producto(
                        descripcion,
                        notify_callback=notify_func or log_notify
                    )
                )

                if resultado["status"] == "completado":
                    prod = resultado.get("producto", {})
                    product_id = prod.get("id", 0)

                    # Recoger archivos generados
                    archivos = []
                    for key in ["pdf", "pptx", "xlsx"]:
                        path = prod.get(key, "")
                        if path:
                            archivos.append(path.split("/")[-1])

                    web_app.web_set_archivos(order_id, archivos, product_id)

                    logger.info(
                        f"Auto-processor: Pedido #{order_id} completado — "
                        f"Producto #{product_id}: {prod.get('nombre', '?')}"
                    )

                    # Notificar exito por Telegram
                    _telegram_notify_sync(
                        f"✅ Auto-procesado pedido #{order_id}\n"
                        f"📦 Producto #{product_id}: {prod.get('nombre', '?')}\n"
                        f"💰 ${prod.get('precio', 0):.2f}\n"
                        f"📄 Archivos: {len(archivos)}\n\n"
                        f"Fija precio con: /web_precio {order_id} MONTO"
                    )

                else:
                    error_msg = resultado.get("error", "Error desconocido")
                    logger.error(f"Auto-processor: Error en pedido #{order_id}: {error_msg}")

                    # Volver a 'recibido' para reintento manual
                    _reset_order_status(order_id)

                    _telegram_notify_sync(
                        f"❌ Error procesando #{order_id}: {error_msg}\n"
                        f"El pedido vuelve a 'recibido'. "
                        f"Puedes procesarlo manual con /web_procesar {order_id}"
                    )

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Auto-processor: Exception en pedido #{order_id}: {e}", exc_info=True)
            _reset_order_status(order_id)
            _telegram_notify_sync(
                f"❌ Error procesando #{order_id}: {e}\n"
                f"El pedido vuelve a 'recibido'. "
                f"Puedes procesarlo manual con /web_procesar {order_id}"
            )


def _reset_order_status(order_id):
    """Resetea un pedido a status 'recibido' despues de un error."""
    try:
        import database as db
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE web_orders SET order_status = 'recibido' WHERE id = ?",
            (order_id,)
        )
        conn.commit()
        logger.info(f"Pedido #{order_id} reseteado a 'recibido'")
    except Exception as e:
        logger.error(f"Error reseteando pedido #{order_id}: {e}")


def _get_telegram_notify(order_id, cliente, descripcion):
    """
    Intenta crear un callback de notificacion via Telegram.
    Retorna None si no se puede (bot no disponible).
    """
    try:
        from config import TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_ID
        if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_USER_ID:
            return None

        async def notify(msg):
            logger.info(f"[Auto #{order_id}] {msg}")

        return notify
    except Exception:
        return None


def _telegram_notify_sync(message):
    """Envia notificacion por Telegram de forma sincrona (best-effort)."""
    try:
        import requests
        from config import TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_ID

        if not TELEGRAM_BOT_TOKEN or not AUTHORIZED_USER_ID:
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": AUTHORIZED_USER_ID,
            "text": message,
            "parse_mode": "HTML",
        }

        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Telegram notify failed: {resp.status_code}")

    except Exception as e:
        logger.warning(f"Telegram notify error: {e}")
