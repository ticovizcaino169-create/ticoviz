"""
TicoViz Corporation v2 — Bot de Telegram (Interfaz de Control)
Todos los departamentos se controlan desde aqui.
Motores: NV8 + Llama 3.1 (Groq) + Gemini Flash + MP4 + MP5 + MP8
Portal Web + Pagos Crypto
"""
import os
import sys
import logging
import asyncio
from pathlib import Path

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)

import database as db
import orchestrator
import ai_engine
from config import TELEGRAM_BOT_TOKEN, AUTHORIZED_USER_ID, MOTORES, DEPARTAMENTOS

# ==================== LOGGING ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ticoviz.bot")


# ==================== SEGURIDAD ====================

def authorized(func):
    """Decorator: solo el usuario autorizado puede usar el bot."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != AUTHORIZED_USER_ID:
            await update.message.reply_text("⛔ Acceso denegado.")
            logger.warning(f"Acceso denegado: {update.effective_user.id}")
            return
        return await func(update, context)
    return wrapper


# ==================== UTILIDADES ====================

async def send_long_message(update: Update, text: str, max_len: int = 4000):
    """Envia mensajes largos dividiendolos en partes."""
    if len(text) <= max_len:
        await update.message.reply_text(text, parse_mode="HTML")
        return
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = max_len
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    for part in parts:
        await update.message.reply_text(part, parse_mode="HTML")
        await asyncio.sleep(0.3)


# ==================== COMANDOS PRINCIPALES ====================

@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida con todos los comandos."""
    welcome = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 TicoViz Corporation v2\n"
        "  Sistema de Creacion y Venta\n"
        "  de Productos Digitales\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🧠 MOTORES ACTIVOS:\n"
        "  🦙 Llama 3.1 (Groq) — Razonamiento\n"
        "  💎 Gemini Flash — Codigo + Docs\n"
        "  🔍 MP4 — Scraper\n"
        "  📚 MP5 — Knowledge Base\n"
        "  🔧 MP8 — QA Agent\n"
        "  🧠 NV8 — Orquestador\n\n"
        "📋 COMANDOS:\n\n"
        "🏭 PRODUCCION\n"
        "  /crear <idea> — Crear producto completo\n"
        "  /productos — Listar productos\n"
        "  /producto <id> — Ver detalle de producto\n"
        "  /codigo <id> — Ver codigo del producto\n\n"
        "🔍 RASTREO\n"
        "  /rastrear <id_producto> — Buscar leads\n"
        "  /leads — Listar leads activos\n\n"
        "🧲 VENTAS\n"
        "  /vender <id_prod> <id_lead> — Iniciar venta\n"
        "  /seguimiento <id_venta> — Follow-up\n"
        "  /ventas — Listar ventas\n\n"
        "🌐 PORTAL WEB\n"
        "  /web_pedidos — Listar pedidos web\n"
        "  /web_pedido <id> — Ver pedido\n"
        "  /web_procesar <id> — Generar producto\n"
        "  /web_precio <id> <monto> — Fijar precio\n"
        "  /web_confirmar <id> — Confirmar pago\n"
        "  /web_cancelar <id> — Cancelar pedido\n\n"
        "📊 SISTEMA\n"
        "  /dashboard — Estado general\n"
        "  /motores — Ver motores activos\n"
        "  /conocimiento — Resumen MP5\n"
        "  /qa <id> — Verificar calidad\n"
        "  /chat <mensaje> — Chat libre con IA\n"
        "  /help — Ver este menu\n"
        "  /ping — Verificar que estoy vivo\n"
    )
    await update.message.reply_text(welcome)


@authorized
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 TicoViz Corporation v2 — Todos los sistemas operativos")


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


# ==================== PRODUCCION ====================

@authorized
async def cmd_crear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crear producto completo con NV8."""
    if not context.args:
        await update.message.reply_text("Uso: /crear <descripcion de la idea>")
        return

    idea = " ".join(context.args)
    await update.message.reply_text(
        f"🧠 NV8: Iniciando creacion de producto...\n"
        f"📝 Idea: {idea[:200]}\n\n"
        f"Esto puede tomar 1-3 minutos. Te ire notificando."
    )

    async def notify(msg):
        await update.message.reply_text(msg)

    resultado = await orchestrator.flujo_crear_producto(idea, notify_callback=notify)

    if resultado["status"] == "completado":
        prod = resultado.get("producto", {})
        await update.message.reply_text(
            f"✅ PRODUCTO CREADO EXITOSAMENTE\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 #{prod.get('id')} — {prod.get('nombre', '')}\n"
            f"📂 {prod.get('categoria', '')}\n"
            f"💰 ${prod.get('precio', 0):.2f} USD\n"
            f"🔧 QA: {prod.get('qa_status', 'N/A')} ({prod.get('qa_score', 0)}/100)\n"
            f"💻 Codigo: {prod.get('codigo_len', 0)} chars\n"
            f"📄 Docs: PDF + PPTX + Excel\n"
            f"🔋 Tokens: {resultado.get('tokens_total', 0)}\n"
            f"🤖 Motores: {', '.join(resultado.get('motores_usados', []))}\n\n"
            f"Usa /producto {prod.get('id')} para ver detalles\n"
            f"Usa /codigo {prod.get('id')} para ver el codigo"
        )
    else:
        await update.message.reply_text(
            f"❌ Error creando producto:\n{resultado.get('error', 'Error desconocido')}"
        )


@authorized
async def cmd_productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listar todos los productos."""
    products = db.get_all_products()
    if not products:
        await update.message.reply_text("📭 No hay productos creados.")
        return

    lines = ["📦 <b>Productos</b>\n"]
    STATUS_ICONS = {"idea": "💡", "en_desarrollo": "⚙️", "listo": "✅", "en_venta": "🏷️", "vendido": "💰"}
    for p in products[:20]:
        icon = STATUS_ICONS.get(p.status, "📦")
        lines.append(f"{icon} #{p.id} | {p.nombre[:40]} | ${p.precio_sugerido:.2f} | {p.status}")
    await send_long_message(update, "\n".join(lines))


@authorized
async def cmd_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver detalle de un producto."""
    if not context.args:
        await update.message.reply_text("Uso: /producto <ID>")
        return
    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID debe ser un numero.")
        return

    p = db.get_product(pid)
    if not p:
        await update.message.reply_text(f"Producto #{pid} no encontrado.")
        return

    text = (
        f"📦 <b>Producto #{p.id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 Nombre: {p.nombre}\n"
        f"📝 {p.descripcion[:300]}\n\n"
        f"📂 Categoria: {p.categoria}\n"
        f"🔧 Tecnologias: {p.tecnologias}\n"
        f"💰 Precio: ${p.precio_sugerido:.2f} USD\n"
        f"📊 Estado: {p.status}\n"
        f"💻 Codigo: {len(p.codigo)} chars\n"
        f"📄 PDF: {'✅' if p.pdf_path else '❌'}\n"
        f"📊 PPTX: {'✅' if p.pptx_path else '❌'}\n"
        f"📈 Excel: {'✅' if p.xlsx_path else '❌'}\n"
        f"🤖 Motor: {p.motor_usado}\n"
        f"🔋 Tokens: {p.tokens_consumidos}\n"
        f"📅 Creado: {p.created_at}\n"
    )
    await send_long_message(update, text)


@authorized
async def cmd_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver codigo de un producto."""
    if not context.args:
        await update.message.reply_text("Uso: /codigo <ID>")
        return
    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID debe ser un numero.")
        return

    p = db.get_product(pid)
    if not p:
        await update.message.reply_text(f"Producto #{pid} no encontrado.")
        return

    if not p.codigo:
        await update.message.reply_text(f"Producto #{pid} no tiene codigo generado.")
        return

    header = f"💻 <b>Codigo — {p.nombre}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    await send_long_message(update, header + p.codigo[:3500])


# ==================== RASTREO ====================

@authorized
async def cmd_rastrear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rastrear leads para un producto."""
    if not context.args:
        await update.message.reply_text("Uso: /rastrear <ID_PRODUCTO>")
        return
    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID debe ser un numero.")
        return

    await update.message.reply_text(f"🔍 MP4: Rastreando leads para producto #{pid}...")

    async def notify(msg):
        await update.message.reply_text(msg)

    resultado = await orchestrator.flujo_rastrear_leads(pid, notify_callback=notify)

    if resultado["status"] == "completado":
        leads = resultado.get("leads", [])
        text = f"🔍 <b>Leads encontrados: {resultado['leads_encontrados']}</b>\n\n"
        for i, l in enumerate(leads[:10], 1):
            text += f"{i}. [{l['plataforma']}] {l['nombre'][:50]} (Score: {l['score']})\n"
        await send_long_message(update, text)
    else:
        await update.message.reply_text(f"❌ Error: {resultado.get('error', '?')}")


@authorized
async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listar leads activos."""
    leads = db.get_all_leads()
    if not leads:
        await update.message.reply_text("📭 No hay leads registrados.")
        return

    lines = ["🔍 <b>Leads Activos</b>\n"]
    for l in leads[:20]:
        lines.append(
            f"#{l.id} | {l.nombre[:35]} | {l.plataforma} | "
            f"Score: {l.score} | {l.status}"
        )
    await send_long_message(update, "\n".join(lines))


# ==================== VENTAS ====================

@authorized
async def cmd_vender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Iniciar venta: /vender <id_producto> <id_lead>"""
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /vender <ID_PRODUCTO> <ID_LEAD>")
        return
    try:
        pid = int(context.args[0])
        lid = int(context.args[1])
    except ValueError:
        await update.message.reply_text("IDs deben ser numeros.")
        return

    await update.message.reply_text(f"🧲 NV8: Iniciando venta P#{pid} -> L#{lid}...")

    async def notify(msg):
        await update.message.reply_text(msg)

    resultado = await orchestrator.flujo_iniciar_venta(pid, lid, notify_callback=notify)

    if resultado["status"] == "completado":
        text = (
            f"✅ <b>Venta #{resultado['venta_id']} Iniciada</b>\n\n"
            f"📧 Asunto: {resultado.get('asunto', 'N/A')}\n\n"
            f"💬 Mensaje:\n{resultado.get('mensaje', '')[:1000]}"
        )
        await send_long_message(update, text)
    else:
        await update.message.reply_text(f"❌ Error: {resultado.get('error', '?')}")


@authorized
async def cmd_seguimiento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generar seguimiento para una venta."""
    if not context.args:
        await update.message.reply_text("Uso: /seguimiento <ID_VENTA>")
        return
    try:
        vid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID debe ser un numero.")
        return

    async def notify(msg):
        await update.message.reply_text(msg)

    resultado = await orchestrator.flujo_seguimiento(vid, notify_callback=notify)

    if resultado["status"] == "completado":
        text = (
            f"📧 <b>Seguimiento #{resultado['seguimiento_num']}</b>\n\n"
            f"💬 Mensaje:\n{resultado.get('mensaje', '')[:1500]}"
        )
        await send_long_message(update, text)
    else:
        await update.message.reply_text(f"❌ Error: {resultado.get('error', '?')}")


@authorized
async def cmd_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listar ventas."""
    sales = db.get_all_sales()
    if not sales:
        await update.message.reply_text("📭 No hay ventas registradas.")
        return

    STATUS_ICONS = {
        "pendiente": "⏳", "mensaje_enviado": "📧", "seguimiento": "🔄",
        "negociando": "💬", "cerrada": "💰", "perdida": "❌",
    }
    lines = ["🧲 <b>Ventas</b>\n"]
    for s in sales[:20]:
        icon = STATUS_ICONS.get(s.status, "❓")
        lines.append(
            f"{icon} #{s.id} | P#{s.product_id} -> L#{s.lead_id} | "
            f"${s.precio_ofrecido:.2f} | {s.status}"
        )
    await send_long_message(update, "\n".join(lines))


# ==================== SISTEMA ====================

@authorized
async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard general del sistema."""
    data = orchestrator.obtener_dashboard()
    if "error" in data:
        await update.message.reply_text(f"❌ Error: {data['error']}")
        return

    p = data.get("productos", {})
    l = data.get("leads", {})
    v = data.get("ventas", {})
    t = data.get("tokens", {})
    k = data.get("conocimiento", {})

    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>DASHBOARD TicoViz v2</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>Productos</b>\n"
        f"  Total: {p.get('total', 0)} | En Venta: {p.get('en_venta', 0)} | "
        f"Vendidos: {p.get('vendidos', 0)}\n\n"
        f"🔍 <b>Leads</b>\n"
        f"  Total: {l.get('total', 0)} | Activos: {l.get('activos', 0)}\n\n"
        f"💰 <b>Ventas</b>\n"
        f"  Total: {v.get('total', 0)} | Cerradas: {v.get('cerradas', 0)} | "
        f"Revenue: ${v.get('revenue', 0):.2f}\n\n"
        f"📚 <b>Conocimiento (MP5)</b>\n"
        f"  Entradas: {k.get('total_entries', 0)}\n\n"
        f"🔋 <b>Tokens</b>\n"
        f"  In: {t.get('total_in', 0):,} | Out: {t.get('total_out', 0):,}\n\n"
        f"🕐 {data.get('timestamp', '')[:19]}\n"
    )
    await send_long_message(update, text)


@authorized
async def cmd_motores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver motores activos del sistema."""
    lines = ["🤖 <b>Motores del Sistema</b>\n"]
    for mid, desc in MOTORES.items():
        lines.append(f"  {desc}")
    lines.append(f"\n🏢 <b>Departamentos</b>\n")
    for did, desc in DEPARTAMENTOS.items():
        lines.append(f"  {desc}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@authorized
async def cmd_conocimiento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumen de la base de conocimiento MP5."""
    resumen = orchestrator.mp5.obtener_resumen()
    text = (
        f"📚 <b>MP5 — Base de Conocimiento</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Total entradas: {resumen.get('total_entries', 0)}\n\n"
    )
    cats = resumen.get("categorias", {})
    if cats:
        text += "📂 <b>Categorias:</b>\n"
        for cat, cnt in cats.items():
            text += f"  {cat}: {cnt}\n"
    recientes = resumen.get("recientes", [])
    if recientes:
        text += "\n🕐 <b>Recientes:</b>\n"
        for r in recientes:
            text += f"  [{r['categoria']}] {r['titulo'][:50]}\n"
    await update.message.reply_text(text, parse_mode="HTML")


@authorized
async def cmd_qa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verificar calidad de un producto con MP8."""
    if not context.args:
        await update.message.reply_text("Uso: /qa <ID_PRODUCTO>")
        return
    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID debe ser un numero.")
        return

    p = db.get_product(pid)
    if not p:
        await update.message.reply_text(f"Producto #{pid} no encontrado.")
        return
    if not p.codigo:
        await update.message.reply_text(f"Producto #{pid} no tiene codigo para verificar.")
        return

    await update.message.reply_text(f"🔧 MP8: Verificando producto #{pid}...")

    async def notify(msg):
        await update.message.reply_text(msg)

    resultado = await orchestrator.mp8.verificar_producto(pid, p.codigo, notify)

    text = (
        f"🔧 <b>Reporte QA — Producto #{pid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Score: {resultado['score_total']}/100\n"
        f"Estado: {'✅ APROBADO' if resultado['aprobado'] else '❌ NO APROBADO'}\n\n"
    )
    for check in resultado.get("checks", []):
        icon = "✅" if check.get("passed") else "❌"
        text += f"{icon} {check.get('tipo', '?')}: {check.get('resumen', '')}\n"
    await send_long_message(update, text)


@authorized
async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat libre con la IA."""
    if not context.args:
        await update.message.reply_text("Uso: /chat <tu mensaje>")
        return

    mensaje = " ".join(context.args)
    await update.message.reply_text("🧠 Pensando...")

    respuesta = await ai_engine.chat_libre(mensaje)
    texto = respuesta.get("text", respuesta.get("respuesta", "Sin respuesta"))
    motor = respuesta.get("_motor", "IA")
    tokens = respuesta.get("_tokens", 0)

    await send_long_message(
        update,
        f"🤖 [{motor}] ({tokens} tokens)\n━━━━━━━━━━━━━━━━━━━━\n{texto}"
    )


# ==================== MAIN ====================

def main():
    """Punto de entrada del bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurado!")
        return

    # Inicializar base de datos
    db.init_database()
    logger.info("Base de datos inicializada")

    # Crear aplicacion
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Registrar handlers principales
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("ping", cmd_ping))
    application.add_handler(CommandHandler("crear", cmd_crear))
    application.add_handler(CommandHandler("productos", cmd_productos))
    application.add_handler(CommandHandler("producto", cmd_producto))
    application.add_handler(CommandHandler("codigo", cmd_codigo))
    application.add_handler(CommandHandler("rastrear", cmd_rastrear))
    application.add_handler(CommandHandler("leads", cmd_leads))
    application.add_handler(CommandHandler("vender", cmd_vender))
    application.add_handler(CommandHandler("seguimiento", cmd_seguimiento))
    application.add_handler(CommandHandler("ventas", cmd_ventas))
    application.add_handler(CommandHandler("dashboard", cmd_dashboard))
    application.add_handler(CommandHandler("motores", cmd_motores))
    application.add_handler(CommandHandler("conocimiento", cmd_conocimiento))
    application.add_handler(CommandHandler("qa", cmd_qa))
    application.add_handler(CommandHandler("chat", cmd_chat))

    # Registrar handlers web
    try:
        from web_commands import get_web_handlers
        for handler in get_web_handlers(authorized):
            application.add_handler(handler)
        logger.info("Web handlers registrados")
    except ImportError:
        logger.warning("web_commands.py no encontrado — handlers web desactivados")

    # Registrar comandos en el menu de Telegram
    async def post_init(app):
        commands = [
            BotCommand("start", "Inicio y menu"),
            BotCommand("crear", "Crear producto con IA"),
            BotCommand("productos", "Listar productos"),
            BotCommand("rastrear", "Buscar leads"),
            BotCommand("vender", "Iniciar venta"),
            BotCommand("dashboard", "Estado del sistema"),
            BotCommand("chat", "Chat libre con IA"),
            BotCommand("web_pedidos", "Pedidos del portal web"),
            BotCommand("ping", "Check sistema"),
            BotCommand("help", "Ver comandos"),
        ]
        await app.bot.set_my_commands(commands)

    application.post_init = post_init

    logger.info("Bot de Telegram iniciando...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
