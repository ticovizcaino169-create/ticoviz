"""
TicoViz Corporation v2 — Comandos de Telegram para Pedidos Web
Agrega estos handlers al bot.py existente.
"""
import logging
import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

import web_app
import orchestrator

logger = logging.getLogger("ticoviz.web_commands")


def get_web_handlers(authorized_decorator):
    """
    Retorna lista de CommandHandlers para pedidos web.
    Uso en bot.py:
        from web_commands import get_web_handlers
        for handler in get_web_handlers(authorized):
            application.add_handler(handler)
    """

    @authorized_decorator
    async def cmd_web_pedidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lista pedidos web recientes."""
        pedidos = web_app.web_listar_pedidos(10)
        if not pedidos:
            await update.message.reply_text("No hay pedidos web.")
            return

        STATUS_ICONS = {
            "recibido": "📩", "procesando": "⚙️", "listo": "✅",
            "entregado": "📦", "cancelado": "❌",
        }
        PAY_ICONS = {
            "pendiente": "⏳", "esperando_confirmacion": "🔍", "pagado": "💚",
        }

        lines = ["📋 <b>Pedidos Web Recientes</b>\n"]
        for p in pedidos:
            s_icon = STATUS_ICONS.get(p["order_status"], "❓")
            p_icon = PAY_ICONS.get(p["payment_status"], "❓")
            precio = p.get("precio", 0) or 0
            lines.append(
                f"{s_icon} #{p['id']} | {p['cliente_nombre']} | "
                f"${precio:.2f} {p_icon} | {p['order_status']}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    @authorized_decorator
    async def cmd_web_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ver detalle de un pedido web."""
        if not context.args:
            await update.message.reply_text("Uso: /web_pedido <ID>")
            return
        try:
            order_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ID debe ser un numero.")
            return

        order = web_app.web_ver_pedido(order_id)
        if not order:
            await update.message.reply_text(f"Pedido #{order_id} no encontrado.")
            return

        precio = order.get("precio", 0) or 0
        text = (
            f"📋 <b>Pedido #{order['id']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Cliente: {order['cliente_nombre']}\n"
            f"📱 Contacto: {order['cliente_contacto']}\n"
            f"📂 Categoria: {order['categoria']}\n"
            f"📝 Descripcion:\n{order['descripcion'][:500]}\n\n"
            f"💵 Precio: ${precio:.2f}\n"
            f"📊 Estado: {order['order_status']}\n"
            f"💳 Pago: {order['payment_status']}\n"
            f"🔗 Token: <code>{order['token']}</code>\n"
            f"📅 Creado: {order['created_at']}\n"
        )
        if order.get("product_id"):
            text += f"📦 Producto: #{order['product_id']}\n"
        if order.get("tx_hash"):
            text += f"🔗 TX Hash: <code>{order['tx_hash']}</code>\n"
        if order.get("notas"):
            text += f"\n📌 Notas: {order['notas'][:200]}\n"

        await update.message.reply_text(text, parse_mode="HTML")

    @authorized_decorator
    async def cmd_web_procesar(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesar un pedido web — genera el producto con NV8."""
        if not context.args:
            await update.message.reply_text("Uso: /web_procesar <ID>")
            return
        try:
            order_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ID debe ser un numero.")
            return

        order = web_app.web_ver_pedido(order_id)
        if not order:
            await update.message.reply_text(f"Pedido #{order_id} no encontrado.")
            return

        web_app.web_procesar_pedido(order_id)
        await update.message.reply_text(
            f"⚙️ Procesando pedido #{order_id}...\n"
            f"NV8 generando producto para: {order['descripcion'][:200]}"
        )

        async def notify(msg):
            await update.message.reply_text(msg)

        try:
            resultado = await orchestrator.flujo_crear_producto(
                order['descripcion'], notify_callback=notify
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

                await update.message.reply_text(
                    f"✅ Producto generado para pedido #{order_id}\n"
                    f"📦 Producto #{product_id}: {prod.get('nombre', '')}\n"
                    f"📄 Archivos: {len(archivos)}\n\n"
                    f"Ahora fija el precio con:\n"
                    f"/web_precio {order_id} MONTO"
                )
            else:
                await update.message.reply_text(
                    f"❌ Error procesando pedido #{order_id}:\n"
                    f"{resultado.get('error', 'Error desconocido')}"
                )
        except Exception as e:
            logger.error(f"Error procesando pedido #{order_id}: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    @authorized_decorator
    async def cmd_web_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fijar precio de un pedido web."""
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /web_precio <ID> <MONTO>")
            return
        try:
            order_id = int(context.args[0])
            precio = float(context.args[1])
        except ValueError:
            await update.message.reply_text("Formato: /web_precio <ID_numero> <MONTO_numero>")
            return

        if precio <= 0:
            await update.message.reply_text("El precio debe ser mayor a 0.")
            return

        success = web_app.web_set_precio(order_id, precio)
        if success:
            order = web_app.web_ver_pedido(order_id)
            await update.message.reply_text(
                f"💵 Precio fijado: ${precio:.2f} USD\n"
                f"📋 Pedido #{order_id} marcado como LISTO\n\n"
                f"El cliente puede pagar en:\n"
                f"/pedido/{order['token']}/pagar"
            )
        else:
            await update.message.reply_text(f"❌ Pedido #{order_id} no encontrado.")

    @authorized_decorator
    async def cmd_web_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirmar pago de un pedido web."""
        if not context.args:
            await update.message.reply_text("Uso: /web_confirmar <ID>")
            return
        try:
            order_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ID debe ser un numero.")
            return

        order = web_app.web_ver_pedido(order_id)
        if not order:
            await update.message.reply_text(f"Pedido #{order_id} no encontrado.")
            return

        if order["payment_status"] != "esperando_confirmacion":
            await update.message.reply_text(
                f"Pedido #{order_id} no tiene pago pendiente de confirmacion.\n"
                f"Estado actual: {order['payment_status']}"
            )
            return

        success = web_app.web_confirmar_pago(order_id)
        if success:
            await update.message.reply_text(
                f"💚 Pago CONFIRMADO — Pedido #{order_id}\n"
                f"📦 Estado: ENTREGADO\n"
                f"El cliente ya puede descargar los archivos."
            )
        else:
            await update.message.reply_text(f"❌ Error confirmando pago.")

    @authorized_decorator
    async def cmd_web_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancelar un pedido web."""
        if not context.args:
            await update.message.reply_text("Uso: /web_cancelar <ID>")
            return
        try:
            order_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("ID debe ser un numero.")
            return

        success = web_app.web_cancelar_pedido(order_id)
        if success:
            await update.message.reply_text(f"❌ Pedido #{order_id} CANCELADO.")
        else:
            await update.message.reply_text(f"Pedido #{order_id} no encontrado.")

    return [
        CommandHandler("web_pedidos", cmd_web_pedidos),
        CommandHandler("web_pedido", cmd_web_pedido),
        CommandHandler("web_procesar", cmd_web_procesar),
        CommandHandler("web_precio", cmd_web_precio),
        CommandHandler("web_confirmar", cmd_web_confirmar),
        CommandHandler("web_cancelar", cmd_web_cancelar),
    ]
