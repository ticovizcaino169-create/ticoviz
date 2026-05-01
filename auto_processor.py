"""
TicoViz Corporation v2 — Auto Processor
Procesa automaticamente pedidos web nuevos cuando llegan.
Se ejecuta en un thread separado, polling cada 60 segundos.

Anti-loop: Cada pedido se intenta MAX 3 veces. Despues se marca
como 'error' y no se reintenta automaticamente.
"""

import logging
import asyncio
import threading
import time
from datetime import datetime

logger = logging.getLogger("ticoviz.auto_processor")

# ============================================================
# CONFIGURACION
# ============================================================
MAX_AUTO_RETRIES = 3        # Maximo intentos automaticos por pedido
POLL_INTERVAL = 60          # Segundos entre cada chequeo
STARTUP_DELAY = 15          # Segundos de espera al arrancar
RETRY_COOLDOWN = 120        # Segundos de cooldown despues de un error

# Registro en memoria de intentos fallidos: {order_id: count}
_failed_attempts = {}
# Pedidos en cooldown: {order_id: timestamp_hasta}
_cooldown_until = {}


def start_auto_processor():
    """
    Lanza el auto-processor en un thread daemon.
    Monitorea pedidos con status 'recibido' y los procesa automaticamente.
    """
    thread = threading.Thread(target=_auto_processor_loop, daemon=True)
    thread.start()
    logger.info(f"Auto-processor iniciado (polling cada {POLL_INTERVAL}s, max {MAX_AUTO_RETRIES} reintentos)")


def _auto_processor_loop():
    """Loop principal del auto-processor."""
    time.sleep(STARTUP_DELAY)
    logger.info("Auto-processor activo — monitoreando pedidos nuevos")

    while True:
        try:
            _check_and_process()
        except Exception as e:
            logger.error(f"Auto-processor error en ciclo: {e}", exc_info=True)

        time.sleep(POLL_INTERVAL)


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

    now = time.time()

    for pedido in pendientes:
        order_id = pedido.get("id")
        descripcion = pedido.get("descripcion", "")
        cliente = pedido.get("cliente_nombre", "desconocido")

        if not descripcion or not descripcion.strip():
            logger.warning(f"Auto-processor: Pedido #{order_id} sin descripcion, saltando")
            continue

        # --- ANTI-LOOP: Verificar intentos previos ---
        attempts = _failed_attempts.get(order_id, 0)

        if attempts >= MAX_AUTO_RETRIES:
            # Ya se intento demasiadas veces — no reintentar
            logger.warning(
                f"Auto-processor: Pedido #{order_id} alcanzo {MAX_AUTO_RETRIES} intentos fallidos. "
                f"Marcando como 'error'. Usa /web_procesar {order_id} para forzar manualmente."
            )
            _mark_order_error(order_id, f"Fallo {MAX_AUTO_RETRIES} veces. Procesar manualmente.")
            _telegram_notify_sync(
                f"⚠️ Pedido #{order_id} fallo {MAX_AUTO_RETRIES} veces consecutivas.\n"
                f"Marcado como 'error'.\n"
                f"Usa /web_procesar {order_id} para intentar manualmente."
            )
            continue

        # --- ANTI-LOOP: Verificar cooldown ---
        cooldown_end = _cooldown_until.get(order_id, 0)
        if now < cooldown_end:
            remaining = int(cooldown_end - now)
            logger.debug(f"Auto-processor: Pedido #{order_id} en cooldown ({remaining}s restantes)")
            continue

        # --- PROCESAR ---
        logger.info(f"Auto-procesando pedido #{order_id} de {cliente} (intento {attempts + 1}/{MAX_AUTO_RETRIES})")

        try:
            # Crear event loop para correr async
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Callback para logging
                async def log_notify(msg):
                    logger.info(f"[Auto #{order_id}] {msg}")

                # Notificar inicio por Telegram
                _telegram_notify_sync(
                    f"🔄 Auto-procesando pedido #{order_id}\n"
                    f"Cliente: {cliente}\n"
                    f"Descripcion: {descripcion[:100]}\n"
                    f"Intento: {attempts + 1}/{MAX_AUTO_RETRIES}"
                )

                resultado = loop.run_until_complete(
                    orchestrator.flujo_crear_producto(
                        descripcion,
                        notify_callback=log_notify
                    )
                )

                if resultado.get("status") == "completado":
                    prod = resultado.get("producto", {})
                    product_id = prod.get("id", 0)

                    # Recoger archivos generados
                    archivos = []
                    for key in ["pdf", "pptx", "xlsx"]:
                        path = prod.get(key, "")
                        if path:
                            archivos.append(path.split("/")[-1])

                    web_app.web_set_archivos(order_id, archivos, product_id)

                    # Limpiar registro de fallos
                    _failed_attempts.pop(order_id, None)
                    _cooldown_until.pop(order_id, None)

                    logger.info(
                        f"Auto-processor: Pedido #{order_id} completado — "
                        f"Producto #{product_id}: {prod.get('nombre', '?')}"
                    )

                    _telegram_notify_sync(
                        f"✅ Pedido #{order_id} completado!\n"
                        f"📦 Producto: {prod.get('nombre', '?')}\n"
                        f"💰 Precio sugerido: ${prod.get('precio', 0):.2f}\n"
                        f"📄 Archivos: {len(archivos)}\n\n"
                        f"Fija precio con: /web_precio {order_id} MONTO"
                    )

                else:
                    error_msg = resultado.get("error", "Error desconocido")
                    logger.error(f"Auto-processor: Error en pedido #{order_id}: {error_msg}")

                    # Registrar intento fallido + cooldown
                    _failed_attempts[order_id] = attempts + 1
                    _cooldown_until[order_id] = now + RETRY_COOLDOWN

                    _telegram_notify_sync(
                        f"❌ Error procesando #{order_id}: {error_msg}\n"
                        f"Intento {attempts + 1}/{MAX_AUTO_RETRIES}. "
                        f"Reintento automatico en {RETRY_COOLDOWN}s.\n"
                        f"O procesar manual: /web_procesar {order_id}"
                    )

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Auto-processor: Exception en pedido #{order_id}: {e}", exc_info=True)

            # Registrar intento fallido + cooldown
            _failed_attempts[order_id] = attempts + 1
            _cooldown_until[order_id] = now + RETRY_COOLDOWN

            _telegram_notify_sync(
                f"❌ Error procesando #{order_id}: {e}\n"
                f"Intento {attempts + 1}/{MAX_AUTO_RETRIES}. "
                f"Reintento en {RETRY_COOLDOWN}s.\n"
                f"O manual: /web_procesar {order_id}"
            )


def _mark_order_error(order_id, error_message):
    """Marca un pedido como 'error' para que no se reintente automaticamente."""
    try:
        import database as db
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE web_orders SET order_status = 'error' WHERE id = ?",
            (order_id,)
        )
        conn.commit()
        logger.info(f"Pedido #{order_id} marcado como 'error'")
    except Exception as e:
        logger.error(f"Error marcando pedido #{order_id} como error: {e}")


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
        }

        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Telegram notify failed: {resp.status_code}")

    except Exception as e:
        logger.warning(f"Telegram notify error: {e}")
