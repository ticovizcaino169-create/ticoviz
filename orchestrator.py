"""
TicoViz Corporation v2 — NV8: Orquestador de Agentes
Coordina todos los motores y departamentos.
Decide que motor usar, ejecuta flujos automaticos.
"""
import logging
import asyncio
import json
from typing import Optional, Callable
from datetime import datetime

import ai_engine
import scraper
import doc_generator
import database as db
from models import Product, Lead, Sale, ProductStatus, LeadStatus, SaleStatus
from knowledge_base import KnowledgeBase
from qa_agent import QAAgent

logger = logging.getLogger("ticoviz.nv8")

# Instancias de motores
mp5 = KnowledgeBase()
mp8 = QAAgent()


# ==================== FLUJO PRINCIPAL: CREAR PRODUCTO ====================

async def flujo_crear_producto(idea: str, notify_callback: Optional[Callable] = None) -> dict:
    """
    NV8 — Flujo automatico completo de creacion de producto:
    1. [MP5] Buscar conocimiento previo relevante
    2. [LLAMA] Analizar idea con razonamiento profundo
    3. [GEMINI] Generar codigo funcional
    4. [MP8] Verificar calidad del codigo
    5. [LLAMA] Calcular precio optimo
    6. [GEMINI] Generar documentos (PDF, PPTX, Excel)
    7. [MP5] Almacenar aprendizaje
    8. [DB] Guardar todo
    """
    resultado = {"status": "en_proceso", "pasos": [], "motores_usados": [],
                 "tokens_total": 0}

    async def notificar(msg):
        logger.info(msg)
        resultado["pasos"].append(msg)
        if notify_callback:
            await notify_callback(msg)

    try:
        # PASO 0: MP5 — Buscar conocimiento previo
        await notificar("MP5: Buscando conocimiento previo relevante...")
        contexto_mp5 = mp5.buscar_contexto(idea)
        if contexto_mp5:
            await notificar("MP5: Encontrado contexto relevante")
        else:
            await notificar("MP5: Sin conocimiento previo — aprendiendo nuevo dominio")

        # PASO 1: LLAMA — Analizar idea
        await notificar("Llama 3.1: Analizando idea con razonamiento profundo...")
        analisis = await ai_engine.analizar_idea(idea, contexto_mp5)
        if "error" in analisis:
            resultado["status"] = "error"
            resultado["error"] = analisis["error"]
            return resultado

        motor_usado = analisis.get("_motor", "LLAMA")
        tokens = analisis.get("_tokens", 0)
        resultado["motores_usados"].append(motor_usado)
        resultado["tokens_total"] += tokens
        db.log_tokens(motor_usado, tokens // 2, tokens // 2, "analizar_idea")

        await notificar(f"Analisis completo: {analisis.get('nombre', 'N/A')} "
                        f"[Motor: {motor_usado}]")

        # PASO 2: DB — Registrar producto
        product = Product(
            nombre=analisis.get("nombre", "Sin nombre"),
            descripcion=analisis.get("descripcion", ""),
            idea_original=idea,
            precio_sugerido=float(analisis.get("precio_sugerido", 0)),
            categoria=analisis.get("categoria", ""),
            tecnologias=analisis.get("tecnologias", ""),
            status=ProductStatus.EN_DESARROLLO.value,
            motor_usado=motor_usado,
            tokens_consumidos=tokens,
        )
        product.id = db.save_product(product)
        db.log_activity("motor", "producto_creado", f"#{product.id} {product.nombre}", motor="NV8")
        await notificar(f"Producto #{product.id} registrado en base de datos")

        # PASO 3: GEMINI — Generar codigo
        await notificar("Gemini Flash: Generando codigo funcional...")
        codigo = await ai_engine.generar_codigo(analisis)
        tokens_code = analisis.get("_tokens", 0)
        resultado["motores_usados"].append("GEMINI")
        resultado["tokens_total"] += tokens_code
        db.log_tokens("GEMINI", tokens_code // 2, tokens_code // 2, "generar_codigo")

        product.codigo = codigo
        db.save_product(product)
        await notificar(f"Codigo generado ({len(codigo)} caracteres) [Motor: GEMINI]")

        # PASO 4: MP8 — Verificar calidad
        await notificar("MP8: Verificando calidad del codigo...")
        qa_result = await mp8.verificar_producto(product.id, codigo, notify_callback)
        qa_score = qa_result.get("score_total", 0)
        qa_status = "APROBADO" if qa_result.get("aprobado") else "OBSERVADO"
        await notificar(f"MP8: {qa_status} (Score: {qa_score}/100)")

        # PASO 5: LLAMA — Calcular precio optimo
        await notificar("Llama 3.1: Calculando precio optimo de mercado...")
        precio_info = await ai_engine.calcular_precio_optimo(analisis)
        tokens_price = precio_info.get("_tokens", 0)
        resultado["tokens_total"] += tokens_price
        db.log_tokens("LLAMA", tokens_price // 2, tokens_price // 2, "calcular_precio")

        precio_final = float(precio_info.get("precio_recomendado",
                                              analisis.get("precio_sugerido", 49)))
        product.precio_sugerido = precio_final
        await notificar(f"Precio optimo calculado: ${precio_final:.2f} USD")

        # PASO 6: Generar documentos
        await notificar("Generando documentos (PDF, PPTX, Excel)...")
        desc_larga = await ai_engine.generar_descripcion_producto(analisis)
        analisis["descripcion_larga"] = desc_larga
        product.analisis_ia = json.dumps(analisis, ensure_ascii=False, default=str)

        docs = doc_generator.generar_paquete_completo(product.id, analisis)
        product.pdf_path = docs.get("pdf", "")
        product.pptx_path = docs.get("pptx", "")
        product.xlsx_path = docs.get("xlsx", "")
        product.status = ProductStatus.LISTO.value
        db.save_product(product)
        await notificar("Documentos generados (PDF + PPTX + Excel)")

        # PASO 7: MP5 — Aprender
        mp5.aprender_de_producto(
            product.nombre, product.categoria,
            product.precio_sugerido, product.tecnologias,
        )
        await notificar("MP5: Conocimiento almacenado para futuras decisiones")

        # PASO 8: Resultado final
        resultado["status"] = "completado"
        resultado["producto"] = {
            "id": product.id,
            "nombre": product.nombre,
            "descripcion": product.descripcion,
            "categoria": product.categoria,
            "tecnologias": product.tecnologias,
            "precio": product.precio_sugerido,
            "codigo_len": len(product.codigo),
            "pdf": product.pdf_path,
            "pptx": product.pptx_path,
            "xlsx": product.xlsx_path,
            "qa_score": qa_score,
            "qa_status": qa_status,
        }
        resultado["motores_usados"] = list(set(resultado["motores_usados"]))

        await notificar(
            f"NV8: PRODUCTO COMPLETADO\n"
            f"  Nombre: {product.nombre}\n"
            f"  Precio: ${product.precio_sugerido:.2f}\n"
            f"  QA: {qa_status} ({qa_score}/100)\n"
            f"  Tokens: {resultado['tokens_total']}\n"
            f"  Motores: {', '.join(resultado['motores_usados'])}"
        )

    except Exception as e:
        logger.error(f"NV8: Error en flujo: {e}", exc_info=True)
        resultado["status"] = "error"
        resultado["error"] = str(e)
        await notificar(f"NV8: ERROR — {e}")

    return resultado


# ==================== FLUJO: RASTREAR LEADS ====================

async def flujo_rastrear_leads(producto_id: int,
                                notify_callback: Optional[Callable] = None) -> dict:
    """Busca leads potenciales para un producto."""
    resultado = {"status": "en_proceso", "leads_encontrados": 0}

    async def notificar(msg):
        logger.info(msg)
        if notify_callback:
            await notify_callback(msg)

    try:
        product = db.get_product(producto_id)
        if not product:
            resultado["status"] = "error"
            resultado["error"] = f"Producto #{producto_id} no encontrado"
            return resultado

        await notificar(f"MP4: Rastreando leads para '{product.nombre}'...")

        leads = scraper.rastrear_y_clasificar(
            product.nombre, product.categoria, product.tecnologias
        )

        saved = 0
        for lead in leads[:10]:
            lead.producto_id = producto_id
            lead_id = db.save_lead(lead)
            if lead_id:
                saved += 1

        db.log_activity("rastreo", "leads_rastreados",
                        f"Producto #{producto_id}: {saved} leads", motor="MP4")

        resultado["status"] = "completado"
        resultado["leads_encontrados"] = saved
        resultado["leads"] = [
            {"nombre": l.nombre[:50], "plataforma": l.plataforma,
             "score": l.score, "url": l.url}
            for l in leads[:10]
        ]

        await notificar(
            f"MP4: Rastreo completo — {saved} leads guardados "
            f"(de {len(leads)} encontrados)"
        )

    except Exception as e:
        logger.error(f"Error rastreando leads: {e}")
        resultado["status"] = "error"
        resultado["error"] = str(e)

    return resultado


# ==================== FLUJO: INICIAR VENTA ====================

async def flujo_iniciar_venta(producto_id: int, lead_id: int,
                               notify_callback: Optional[Callable] = None) -> dict:
    """Inicia proceso de venta generando pitch personalizado."""
    resultado = {"status": "en_proceso"}

    async def notificar(msg):
        logger.info(msg)
        if notify_callback:
            await notify_callback(msg)

    try:
        product = db.get_product(producto_id)
        lead = db.get_lead(lead_id)

        if not product:
            return {"status": "error", "error": f"Producto #{producto_id} no encontrado"}
        if not lead:
            return {"status": "error", "error": f"Lead #{lead_id} no encontrado"}

        await notificar(f"Llama 3.1: Generando pitch de venta personalizado...")

        pitch = await ai_engine.generar_pitch_venta(
            producto_nombre=product.nombre,
            producto_descripcion=product.descripcion,
            lead_necesidad=lead.necesidad,
            lead_plataforma=lead.plataforma,
            precio=product.precio_sugerido,
        )
        tokens = pitch.get("_tokens", 0)
        db.log_tokens("LLAMA", tokens // 2, tokens // 2, "pitch_venta")

        # Crear venta
        sale = Sale(
            product_id=producto_id,
            lead_id=lead_id,
            mensaje_enviado=pitch.get("mensaje", ""),
            precio_ofrecido=product.precio_sugerido,
            status=SaleStatus.MENSAJE_ENVIADO.value,
        )
        sale.id = db.save_sale(sale)

        # Actualizar lead
        lead.status = LeadStatus.CONTACTADO.value
        db.save_lead(lead)

        db.log_activity("ventas", "venta_iniciada",
                        f"Venta #{sale.id}: P#{producto_id} -> L#{lead_id}", motor="NV8")

        resultado["status"] = "completado"
        resultado["venta_id"] = sale.id
        resultado["mensaje"] = pitch.get("mensaje", "")
        resultado["asunto"] = pitch.get("asunto", "")

        await notificar(
            f"NV8: Venta #{sale.id} iniciada\n"
            f"  Producto: {product.nombre}\n"
            f"  Lead: {lead.nombre[:40]}\n"
            f"  Precio: ${product.precio_sugerido:.2f}"
        )

    except Exception as e:
        logger.error(f"Error iniciando venta: {e}")
        resultado["status"] = "error"
        resultado["error"] = str(e)

    return resultado


# ==================== FLUJO: SEGUIMIENTO ====================

async def flujo_seguimiento(venta_id: int,
                             notify_callback: Optional[Callable] = None) -> dict:
    """Genera mensaje de seguimiento para una venta."""
    resultado = {"status": "en_proceso"}

    async def notificar(msg):
        logger.info(msg)
        if notify_callback:
            await notify_callback(msg)

    try:
        sale = db.get_sale(venta_id)
        if not sale:
            return {"status": "error", "error": f"Venta #{venta_id} no encontrada"}

        product = db.get_product(sale.product_id)
        lead = db.get_lead(sale.lead_id)

        await notificar(f"Llama 3.1: Generando seguimiento #{sale.seguimientos + 1}...")

        seguimiento = await ai_engine.generar_seguimiento(
            producto_nombre=product.nombre if product else "Producto",
            mensaje_anterior=sale.mensaje_enviado,
            respuesta_lead=sale.respuesta,
            numero_seguimiento=sale.seguimientos + 1,
        )
        tokens = seguimiento.get("_tokens", 0)
        db.log_tokens("LLAMA", tokens // 2, tokens // 2, "seguimiento")

        # Actualizar venta
        sale.seguimientos += 1
        sale.status = SaleStatus.SEGUIMIENTO.value
        sale.mensaje_enviado = seguimiento.get("mensaje", sale.mensaje_enviado)
        db.save_sale(sale)

        db.log_activity("ventas", "seguimiento",
                        f"Venta #{venta_id}: Seguimiento #{sale.seguimientos}", motor="NV8")

        resultado["status"] = "completado"
        resultado["mensaje"] = seguimiento.get("mensaje", "")
        resultado["seguimiento_num"] = sale.seguimientos

        await notificar(f"NV8: Seguimiento #{sale.seguimientos} generado para venta #{venta_id}")

    except Exception as e:
        logger.error(f"Error en seguimiento: {e}")
        resultado["status"] = "error"
        resultado["error"] = str(e)

    return resultado


# ==================== DASHBOARD ====================

def obtener_dashboard() -> dict:
    """Genera datos del dashboard del sistema."""
    try:
        stats = db.get_system_stats()
        knowledge = mp5.obtener_resumen()

        return {
            "productos": {
                "total": stats.total_products,
                "en_venta": stats.products_en_venta,
                "vendidos": stats.products_vendidos,
            },
            "leads": {
                "total": stats.total_leads,
                "activos": stats.leads_activos,
            },
            "ventas": {
                "total": stats.total_sales,
                "cerradas": stats.sales_cerradas,
                "revenue": stats.total_revenue,
            },
            "conocimiento": knowledge,
            "tokens": {
                "total_in": stats.total_tokens_in,
                "total_out": stats.total_tokens_out,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error generando dashboard: {e}")
        return {"error": str(e)}
