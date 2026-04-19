"""
TicoViz Corporation v2 — Launcher Principal (Railway)
Inicia Bot de Telegram + Portal Web + Auto Processor.
Railway asigna PORT dinamicamente via variable de entorno.
"""
import sys
import logging
import threading
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ticoviz.main")


def start_web_server():
    """Inicia Flask en un thread separado."""
    try:
        from web_app import create_app
        from config import WEB_PORT, WEB_HOST

        app = create_app()
        logger.info(f"Portal Web iniciando en {WEB_HOST}:{WEB_PORT}")
        app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Error en Portal Web: {e}")
        raise


def start_auto_processor():
    """Inicia el auto-processor en un thread separado."""
    try:
        from auto_processor import start_auto_processor as _start
        _start()
        logger.info("Auto-processor lanzado")
    except Exception as e:
        logger.error(f"Error en Auto-processor: {e}")


def start_telegram_bot():
    """Inicia el bot de Telegram en el thread principal."""
    try:
        import bot
        logger.info("Iniciando Bot de Telegram...")
        bot.main()
    except ImportError:
        logger.warning(
            "bot.py no encontrado. Ejecutando solo el Portal Web. "
            "Copia bot.py para activar el bot de Telegram."
        )
        import time
        while True:
            time.sleep(60)
    except Exception as e:
        logger.error(f"Error en Bot de Telegram: {e}")
        raise


def main():
    """Punto de entrada principal. Lanza web + auto-processor + bot."""
    logger.info("=" * 50)
    logger.info("TicoViz Corporation v2 — Iniciando Sistema")
    logger.info(f"PORT: {os.getenv('PORT', 'no definido (usando default)')}")
    logger.info(f"RAILWAY: {'Si' if os.getenv('RAILWAY_ENVIRONMENT') else 'No (local)'}")
    logger.info("=" * 50)

    # Web server en thread separado (daemon = se cierra con el main)
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    logger.info("Portal Web lanzado en thread separado")

    # Auto-processor en thread separado
    start_auto_processor()

    # Bot de Telegram en thread principal (bloqueante)
    start_telegram_bot()


if __name__ == "__main__":
    main()
