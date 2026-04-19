"""
TicoViz Corporation v2 — Motor de IA Dual
Llama 3.1 (Groq) = Razonamiento profundo + analisis de mercado
Gemini Flash     = Codigo + documentos + respuestas rapidas
NV8 decide que motor usar segun la tarea.
"""
import logging
import json
import aiohttp
import asyncio
from typing import Optional

from config import (
    GROQ_API_KEY, GROQ_MODEL, GROQ_API_URL,
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_API_URL,
)

logger = logging.getLogger("ticoviz.ai")


# ==================== CLIENTE GROQ (Llama 3.1) ====================

async def _call_groq(messages: list, temperature: float = 0.7,
                     max_tokens: int = 4096) -> dict:
    if not GROQ_API_KEY:
        return {"text": "[ERROR] GROQ_API_KEY no configurada", "tokens_in": 0, "tokens_out": 0}
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_API_URL, json=payload,
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Groq API error {resp.status}: {error_text[:300]}")
                    return {"text": f"[ERROR Groq {resp.status}]", "tokens_in": 0, "tokens_out": 0}
                data = await resp.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "text": text,
                    "tokens_in": usage.get("prompt_tokens", 0),
                    "tokens_out": usage.get("completion_tokens", 0),
                }
    except asyncio.TimeoutError:
        logger.error("Groq API timeout")
        return {"text": "[ERROR] Groq timeout", "tokens_in": 0, "tokens_out": 0}
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return {"text": f"[ERROR] {e}", "tokens_in": 0, "tokens_out": 0}


# ==================== CLIENTE GEMINI ====================

async def _call_gemini(prompt: str, system_instruction: str = "",
                       temperature: float = 0.7, max_tokens: int = 8192) -> dict:
    if not GEMINI_API_KEY:
        return {"text": "[ERROR] GEMINI_API_KEY no configurada", "tokens_in": 0, "tokens_out": 0}
    url = f"{GEMINI_API_URL}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    contents = [{"parts": [{"text": prompt}]}]
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=90)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Gemini API error {resp.status}: {error_text[:300]}")
                    return {"text": f"[ERROR Gemini {resp.status}]", "tokens_in": 0, "tokens_out": 0}
                data = await resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                usage = data.get("usageMetadata", {})
                return {
                    "text": text,
                    "tokens_in": usage.get("promptTokenCount", 0),
                    "tokens_out": usage.get("candidatesTokenCount", 0),
                }
    except asyncio.TimeoutError:
        logger.error("Gemini API timeout")
        return {"text": "[ERROR] Gemini timeout", "tokens_in": 0, "tokens_out": 0}
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return {"text": f"[ERROR] {e}", "tokens_in": 0, "tokens_out": 0}


# ==================== SELECTOR DE MOTOR ====================

async def _call_smart(task_type: str, prompt: str,
                      system_instruction: str = "",
                      temperature: float = 0.7) -> dict:
    """NV8 decide que motor usar segun la tarea."""
    use_groq = task_type in ("analisis", "precio", "venta", "seguimiento", "chat", "lead")
    if use_groq and GROQ_API_KEY:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        result = await _call_groq(messages, temperature=temperature)
        result["_motor"] = "LLAMA"
        result["_tokens"] = result["tokens_in"] + result["tokens_out"]
        if not result["text"].startswith("[ERROR"):
            return result
        logger.warning("Groq fallo, fallback a Gemini")
    result = await _call_gemini(prompt, system_instruction, temperature=temperature)
    result["_motor"] = "GEMINI"
    result["_tokens"] = result["tokens_in"] + result["tokens_out"]
    return result


def _parse_json(text: str) -> dict:
    """Extrae JSON de una respuesta que puede tener markdown."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "No se pudo parsear JSON", "raw": text[:500]}


# ==================== FUNCIONES DE NEGOCIO ====================

async def analizar_idea(idea: str, contexto_mp5: str = "") -> dict:
    system = (
        "Eres un analista de productos digitales experto. "
        "Evaluas ideas y generas analisis de mercado concisos y accionables. "
        "Siempre respondes en JSON valido."
    )
    prompt = f"""{contexto_mp5}
Analiza esta idea de producto digital y devuelve un JSON con esta estructura exacta:
{{
    "nombre": "nombre comercial atractivo",
    "descripcion": "descripcion de venta en 2-3 lineas, persuasiva",
    "categoria": "app|juego|herramienta|api|template|saas|bot|otro",
    "tecnologias": "tecnologias principales separadas por coma",
    "publico_objetivo": "quien lo compraria",
    "precio_sugerido": numero en USD (realista para producto digital),
    "potencial": "bajo|medio|alto",
    "razon_precio": "por que ese precio",
    "features_clave": ["feature1", "feature2", "feature3"],
    "competencia": "competidores similares y como diferenciarse"
}}

IDEA: {idea}

Responde SOLO con el JSON, sin markdown ni texto adicional."""
    result = await _call_smart("analisis", prompt, system)
    parsed = _parse_json(result["text"])
    parsed["_motor"] = result.get("_motor", "")
    parsed["_tokens"] = result.get("_tokens", 0)
    return parsed


async def generar_codigo(analisis: dict) -> str:
    system = (
        "Eres un programador senior experto. "
        "Generas codigo limpio, funcional, bien documentado y listo para produccion. "
        "Siempre incluyes todos los imports necesarios."
    )
    prompt = f"""Genera el codigo completo y funcional para este producto digital:

NOMBRE: {analisis.get('nombre', 'Producto')}
DESCRIPCION: {analisis.get('descripcion', '')}
CATEGORIA: {analisis.get('categoria', '')}
TECNOLOGIAS: {analisis.get('tecnologias', 'Python')}
FEATURES: {analisis.get('features_clave', [])}

Requisitos:
1. Codigo COMPLETO y funcional (no snippets parciales)
2. Bien documentado con docstrings
3. Manejo de errores
4. Listo para ejecutar sin modificaciones
5. Si es una app web, usa Flask o FastAPI
6. Si es un bot, usa python-telegram-bot
7. Incluye un README.md como comentario al final

Devuelve SOLO el codigo, sin explicaciones adicionales."""
    result = await _call_smart("codigo", prompt, system)
    code = result["text"].strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return code


async def generar_pitch_venta(producto: dict) -> str:
    system = (
        "Eres un vendedor experto en productos digitales. "
        "Usas psicologia de persuasion, urgencia y prueba social. "
        "No suenas como un robot. Eres directo, conciso y orientado a cerrar."
    )
    prompt = f"""Crea un pitch de venta para enviar por mensaje directo a un cliente potencial.

PRODUCTO: {producto.get('nombre', '')}
DESCRIPCION: {producto.get('descripcion', '')}
PRECIO: ${producto.get('precio_sugerido', 0)} USD
CATEGORIA: {producto.get('categoria', '')}
FEATURES: {producto.get('features_clave', [])}

Requisitos:
1. Maximo 200 palabras
2. Empieza con un hook que capture atencion
3. Menciona 2-3 beneficios concretos
4. Incluye una llamada a la accion clara
5. Tono profesional pero humano, NO spam
6. Maximo 3 emojis
7. Termina con pregunta para abrir conversacion

Devuelve SOLO el mensaje de venta."""
    result = await _call_smart("venta", prompt, system)
    return result["text"].strip()


async def generar_descripcion_producto(producto: dict) -> str:
    system = (
        "Eres un copywriter profesional de productos tecnologicos. "
        "Creas descripciones detalladas, tecnicas pero accesibles."
    )
    prompt = f"""Crea una descripcion profesional detallada para este producto digital:

NOMBRE: {producto.get('nombre', '')}
CATEGORIA: {producto.get('categoria', '')}
FEATURES: {producto.get('features_clave', [])}
TECNOLOGIAS: {producto.get('tecnologias', '')}

Incluye: Resumen ejecutivo, problema que resuelve, solucion, caracteristicas,
arquitectura tecnica, beneficios, casos de uso.
Formato: texto plano, bien estructurado."""
    result = await _call_smart("analisis", prompt, system)
    return result["text"].strip()


async def calcular_precio_optimo(producto: dict, mercado_info: str = "") -> dict:
    system = (
        "Eres un analista financiero experto en pricing de productos digitales. "
        "Siempre respondes en JSON valido."
    )
    prompt = f"""Calcula el precio optimo para este producto digital:

NOMBRE: {producto.get('nombre', '')}
CATEGORIA: {producto.get('categoria', '')}
FEATURES: {producto.get('features_clave', [])}
INFO MERCADO: {mercado_info or 'No disponible'}

Devuelve JSON:
{{
    "precio_minimo": numero,
    "precio_sugerido": numero,
    "precio_premium": numero,
    "moneda": "USD",
    "estrategia": "penetracion|valor|premium|freemium",
    "justificacion": "por que este precio",
    "descuento_lanzamiento": porcentaje,
    "precio_lanzamiento": numero con descuento
}}

Responde SOLO con JSON valido."""
    result = await _call_smart("precio", prompt, system)
    parsed = _parse_json(result["text"])
    parsed["_motor"] = result.get("_motor", "")
    parsed["_tokens"] = result.get("_tokens", 0)
    return parsed


async def analizar_lead(lead_info: str) -> dict:
    system = (
        "Eres un analista de ventas B2B experto. "
        "Calificas leads por viabilidad y potencial de cierre. "
        "Siempre respondes en JSON valido."
    )
    prompt = f"""Analiza este lead potencial:

{lead_info}

Devuelve JSON:
{{
    "score": numero 1-100,
    "presupuesto_estimado": numero USD,
    "urgencia": "baja|media|alta",
    "probabilidad_cierre": porcentaje,
    "estrategia_contacto": "como abordar",
    "mensaje_sugerido": "primer mensaje personalizado",
    "objeciones_probables": ["objecion1"],
    "respuestas_objeciones": ["respuesta1"]
}}

Responde SOLO con JSON valido."""
    result = await _call_smart("lead", prompt, system)
    parsed = _parse_json(result["text"])
    parsed["_motor"] = result.get("_motor", "")
    parsed["_tokens"] = result.get("_tokens", 0)
    return parsed


async def generar_seguimiento(venta_info: dict, intento: int) -> str:
    estrategias = {
        1: "Recordatorio amable con valor adicional",
        2: "Caso de estudio o testimonio relevante",
        3: "Oferta limitada o descuento por tiempo",
        4: "Ultimo contacto, directo y sin presion"
    }
    estrategia = estrategias.get(intento, estrategias[4])
    system = (
        "Eres un vendedor experto en follow-up. "
        "Cada seguimiento es diferente y aporta algo nuevo. "
        "Nunca suenas desesperado."
    )
    prompt = f"""Genera follow-up #{intento} para esta venta:

PRODUCTO: {venta_info.get('producto', '')}
PRECIO: ${venta_info.get('precio', 0)}
MENSAJE ANTERIOR: {venta_info.get('mensaje_anterior', 'Pitch inicial')}
RESPUESTA CLIENTE: {venta_info.get('respuesta', 'Sin respuesta')}
ESTRATEGIA: {estrategia}

Maximo 100 palabras. NO repitas pitch. Aporta algo NUEVO.
Termina con pregunta o call-to-action."""
    result = await _call_smart("seguimiento", prompt, system)
    return result["text"].strip()


async def verificar_codigo(codigo: str) -> dict:
    system = (
        "Eres un code reviewer senior. Evaluas calidad, seguridad y funcionalidad. "
        "Respondes en JSON valido."
    )
    prompt = f"""Analiza este codigo y devuelve JSON:
{{
    "calidad": numero 1-10,
    "resumen": "resumen en 2 lineas",
    "errores": ["error1"],
    "sugerencias": ["sugerencia1"],
    "seguridad": "buena|aceptable|mala"
}}

CODIGO:
{codigo[:3000]}

Responde SOLO con JSON."""
    result = await _call_smart("codigo", prompt, system)
    parsed = _parse_json(result["text"])
    parsed["_tokens"] = result.get("_tokens", 0)
    return parsed


async def manejar_objeciones(objecion: str, producto_info: dict) -> str:
    system = (
        "Eres un experto en manejo de objeciones de venta. "
        "Respondes con empatia, datos y redireccion al valor."
    )
    prompt = f"""El cliente dijo: "{objecion}"

PRODUCTO: {producto_info.get('nombre', '')}
PRECIO: ${producto_info.get('precio', 0)}

Genera una respuesta persuasiva en maximo 100 palabras que:
1. Valide la preocupacion
2. Reencuadre con datos
3. Cierre con pregunta de avance"""
    result = await _call_smart("venta", prompt, system)
    return result["text"].strip()


async def chat_libre(mensaje: str, contexto: str = "") -> str:
    system = (
        "Eres el asistente central de TicoViz Corporation. "
        "Ayudas con cualquier consulta sobre el negocio de venta de productos digitales. "
        "Eres directo, practico y orientado a resultados. Responde en espanol."
    )
    prompt = f"""{'CONTEXTO: ' + contexto + chr(10) if contexto else ''}CONSULTA: {mensaje}"""
    result = await _call_smart("chat", prompt, system)
    return result["text"].strip()
