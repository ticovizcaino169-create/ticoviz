"""
TicoViz Corporation v2 — AI Engine
Motores de IA: Llama 3.1 (Groq) + Gemini Flash (Google)

Funciones:
  - analizar_idea        (LLAMA)  → Analisis profundo de idea
  - generar_codigo        (GEMINI) → Codigo funcional
  - calcular_precio_optimo(LLAMA)  → Precio de mercado
  - generar_descripcion_producto (GEMINI) → Descripcion larga
  - generar_pitch_venta   (LLAMA)  → Mensaje de venta
  - generar_seguimiento   (LLAMA)  → Follow-up de venta
  - chat_libre            (LLAMA)  → Chat abierto
  - extract_json          (util)   → Parser robusto de JSON desde LLM
"""

import json
import re
import logging
import aiohttp
from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_API_URL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_API_URL,
)

logger = logging.getLogger("ticoviz.ai_engine")


# ============================================================
# JSON PARSER ROBUSTO
# ============================================================

def extract_json(text):
    """
    Extrae y parsea JSON de una respuesta de LLM que puede contener
    markdown code blocks, texto extra antes/despues, etc.
    """
    if not text or not text.strip():
        raise ValueError("Empty AI response")

    cleaned = text.strip()

    # Paso 1: Quitar bloques de codigo markdown
    cleaned = re.sub(r'```(?:json)?\s*\n?', '', cleaned)
    cleaned = cleaned.strip()

    # Paso 2: Intento directo
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Paso 3: Buscar JSON object entre primer { y ultimo }
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end + 1])
            logger.info(f"[AI Parser] JSON extracted after cleanup from: {text[:100]}...")
            return result
        except json.JSONDecodeError:
            pass

    # Paso 4: Buscar JSON array entre primer [ y ultimo ]
    start = cleaned.find('[')
    end = cleaned.rfind(']')
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end + 1])
            logger.info(f"[AI Parser] JSON array extracted after cleanup from: {text[:100]}...")
            return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in AI response: {text[:300]}")


# ============================================================
# LLAMADAS A APIs
# ============================================================

async def _call_groq(messages, temperature=0.7, max_tokens=4096):
    """Llama a Groq API (Llama 3.1) — formato OpenAI compatible."""
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
            async with session.post(GROQ_API_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Groq API error {resp.status}: {error_text[:500]}")
                    return {"error": f"Groq API error: {resp.status}", "_motor": "LLAMA", "_tokens": 0}

                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {})
                total_tokens = tokens.get("total_tokens", 0)

                return {"_raw": content, "_motor": "LLAMA", "_tokens": total_tokens}

    except aiohttp.ClientError as e:
        logger.error(f"Groq connection error: {e}")
        return {"error": f"Connection error: {e}", "_motor": "LLAMA", "_tokens": 0}
    except Exception as e:
        logger.error(f"Groq unexpected error: {e}")
        return {"error": str(e), "_motor": "LLAMA", "_tokens": 0}


async def _call_gemini(prompt, temperature=0.7, max_tokens=8192):
    """Llama a Gemini Flash API."""
    url = f"{GEMINI_API_URL}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Gemini API error {resp.status}: {error_text[:500]}")
                    return {"error": f"Gemini API error: {resp.status}", "_motor": "GEMINI", "_tokens": 0}

                data = await resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return {"error": "Gemini: no candidates returned", "_motor": "GEMINI", "_tokens": 0}

                content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                tokens_meta = data.get("usageMetadata", {})
                total_tokens = tokens_meta.get("totalTokenCount", 0)

                return {"_raw": content, "_motor": "GEMINI", "_tokens": total_tokens}

    except aiohttp.ClientError as e:
        logger.error(f"Gemini connection error: {e}")
        return {"error": f"Connection error: {e}", "_motor": "GEMINI", "_tokens": 0}
    except Exception as e:
        logger.error(f"Gemini unexpected error: {e}")
        return {"error": str(e), "_motor": "GEMINI", "_tokens": 0}


# ============================================================
# FUNCIONES PRINCIPALES
# ============================================================

async def analizar_idea(idea: str, contexto_previo: str = None) -> dict:
    """
    Analiza una idea de producto digital con Llama 3.1.
    Retorna dict con: nombre, descripcion, precio_sugerido, categoria,
    tecnologias, funcionalidades, _motor, _tokens.
    """
    contexto = ""
    if contexto_previo:
        contexto = f"\n\nCONTEXTO PREVIO (conocimiento interno):\n{contexto_previo}\n"

    messages = [
        {
            "role": "system",
            "content": (
                "Eres el motor de analisis de TicoViz Corporation. "
                "Analizas ideas de productos digitales y devuelves un JSON estructurado. "
                "SIEMPRE responde UNICAMENTE con JSON valido, sin texto adicional ni markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Analiza esta idea de producto digital y devuelve SOLO un JSON con esta estructura exacta:\n"
                f'{{\n'
                f'  "nombre": "Nombre del producto",\n'
                f'  "descripcion": "Descripcion corta (1-2 oraciones)",\n'
                f'  "precio_sugerido": 49.99,\n'
                f'  "categoria": "app|bot|herramienta|juego|api|template|saas|automatizacion|otro",\n'
                f'  "tecnologias": "Python, Flask, React, etc",\n'
                f'  "funcionalidades": ["func1", "func2", "func3"],\n'
                f'  "complejidad": "baja|media|alta",\n'
                f'  "tiempo_estimado": "2-3 dias"\n'
                f'}}\n\n'
                f"IDEA: {idea}"
                f"{contexto}"
            ),
        },
    ]

    result = await _call_groq(messages, temperature=0.4)

    if "error" in result:
        return result

    try:
        parsed = extract_json(result["_raw"])
        parsed["_motor"] = result["_motor"]
        parsed["_tokens"] = result["_tokens"]
        return parsed
    except (ValueError, KeyError) as e:
        logger.error(f"analizar_idea parse error: {e}")
        return {"error": f"No se pudo parsear JSON: {e}", "_motor": "LLAMA", "_tokens": result.get("_tokens", 0)}


async def generar_codigo(analisis: dict) -> str:
    """
    Genera codigo funcional con Gemini Flash basado en el analisis.
    Retorna string con el codigo.
    """
    nombre = analisis.get("nombre", "Producto")
    descripcion = analisis.get("descripcion", "")
    tecnologias = analisis.get("tecnologias", "Python")
    funcionalidades = analisis.get("funcionalidades", [])

    funcs_text = "\n".join(f"- {f}" for f in funcionalidades) if funcionalidades else "- Funcionalidad principal"

    prompt = (
        f"Genera el codigo completo y funcional para el siguiente producto digital:\n\n"
        f"NOMBRE: {nombre}\n"
        f"DESCRIPCION: {descripcion}\n"
        f"TECNOLOGIAS: {tecnologias}\n"
        f"FUNCIONALIDADES:\n{funcs_text}\n\n"
        f"REQUISITOS:\n"
        f"- Codigo completo, funcional y listo para ejecutar\n"
        f"- Incluir imports necesarios\n"
        f"- Incluir comentarios explicativos\n"
        f"- Incluir instrucciones de uso al final como comentario\n"
        f"- NO incluir explicaciones fuera del codigo, solo el codigo\n"
    )

    result = await _call_gemini(prompt, temperature=0.3, max_tokens=8192)

    if "error" in result:
        return f"# Error generando codigo: {result['error']}\npass"

    code = result.get("_raw", "# Sin codigo generado\npass")

    # Limpiar markdown code blocks si vienen
    code = re.sub(r'```(?:python|javascript|html|css|java|cpp|c)?\s*\n?', '', code)
    code = code.strip()

    return code


async def calcular_precio_optimo(analisis: dict) -> dict:
    """
    Calcula precio optimo de mercado con Llama 3.1.
    Retorna dict con: precio_recomendado, justificacion, rango_min, rango_max, _tokens.
    """
    nombre = analisis.get("nombre", "Producto")
    categoria = analisis.get("categoria", "otro")
    complejidad = analisis.get("complejidad", "media")
    tecnologias = analisis.get("tecnologias", "")
    precio_sugerido = analisis.get("precio_sugerido", 49)

    messages = [
        {
            "role": "system",
            "content": (
                "Eres un experto en pricing de productos digitales. "
                "Analiza el producto y sugiere un precio optimo basado en el mercado. "
                "SIEMPRE responde UNICAMENTE con JSON valido."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Calcula el precio optimo para este producto digital:\n\n"
                f"Nombre: {nombre}\n"
                f"Categoria: {categoria}\n"
                f"Complejidad: {complejidad}\n"
                f"Tecnologias: {tecnologias}\n"
                f"Precio sugerido inicial: ${precio_sugerido}\n\n"
                f"Responde SOLO con JSON:\n"
                f'{{\n'
                f'  "precio_recomendado": 59.99,\n'
                f'  "justificacion": "Razon del precio",\n'
                f'  "rango_min": 29.99,\n'
                f'  "rango_max": 99.99\n'
                f'}}'
            ),
        },
    ]

    result = await _call_groq(messages, temperature=0.3)

    if "error" in result:
        return {"precio_recomendado": precio_sugerido, "_tokens": 0, **result}

    try:
        parsed = extract_json(result["_raw"])
        parsed["_tokens"] = result["_tokens"]
        parsed["_motor"] = result["_motor"]
        return parsed
    except (ValueError, KeyError) as e:
        logger.error(f"calcular_precio parse error: {e}")
        return {"precio_recomendado": precio_sugerido, "_tokens": result.get("_tokens", 0), "_motor": "LLAMA"}


async def generar_descripcion_producto(analisis: dict) -> str:
    """
    Genera descripcion larga del producto con Gemini Flash.
    Retorna string con la descripcion.
    """
    nombre = analisis.get("nombre", "Producto")
    descripcion = analisis.get("descripcion", "")
    funcionalidades = analisis.get("funcionalidades", [])
    tecnologias = analisis.get("tecnologias", "")

    funcs = ", ".join(funcionalidades) if funcionalidades else "N/A"

    prompt = (
        f"Genera una descripcion profesional y detallada para este producto digital:\n\n"
        f"Nombre: {nombre}\n"
        f"Descripcion corta: {descripcion}\n"
        f"Funcionalidades: {funcs}\n"
        f"Tecnologias: {tecnologias}\n\n"
        f"La descripcion debe tener 3-4 parrafos, ser persuasiva y profesional. "
        f"Incluir beneficios, casos de uso, y diferenciadores. "
        f"Solo texto, sin markdown ni formato especial."
    )

    result = await _call_gemini(prompt, temperature=0.6)

    if "error" in result:
        return descripcion or f"Producto digital: {nombre}"

    return result.get("_raw", descripcion).strip()


async def generar_pitch_venta(producto_nombre: str, producto_descripcion: str,
                               lead_necesidad: str, lead_plataforma: str,
                               precio: float) -> dict:
    """
    Genera pitch de venta personalizado con Llama 3.1.
    Retorna dict con: mensaje, asunto, _tokens.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Eres un experto en ventas B2B de productos digitales. "
                "Genera mensajes de venta personalizados, cortos y efectivos. "
                "SIEMPRE responde UNICAMENTE con JSON valido."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Genera un pitch de venta personalizado:\n\n"
                f"PRODUCTO: {producto_nombre}\n"
                f"DESCRIPCION: {producto_descripcion[:300]}\n"
                f"PRECIO: ${precio:.2f} USD\n\n"
                f"LEAD:\n"
                f"- Necesidad detectada: {lead_necesidad}\n"
                f"- Plataforma: {lead_plataforma}\n\n"
                f"Responde SOLO con JSON:\n"
                f'{{\n'
                f'  "asunto": "Asunto del mensaje",\n'
                f'  "mensaje": "Cuerpo del mensaje de venta (2-3 parrafos)"\n'
                f'}}'
            ),
        },
    ]

    result = await _call_groq(messages, temperature=0.6)

    if "error" in result:
        return {"mensaje": f"Hola, tenemos {producto_nombre} por ${precio:.2f}.", "asunto": producto_nombre, **result}

    try:
        parsed = extract_json(result["_raw"])
        parsed["_tokens"] = result["_tokens"]
        parsed["_motor"] = result["_motor"]
        return parsed
    except (ValueError, KeyError) as e:
        logger.error(f"generar_pitch parse error: {e}")
        return {
            "mensaje": f"Hola, tenemos {producto_nombre} por ${precio:.2f}.",
            "asunto": producto_nombre,
            "_tokens": result.get("_tokens", 0),
            "_motor": "LLAMA",
        }


async def generar_seguimiento(producto_nombre: str, mensaje_anterior: str,
                                respuesta_lead: str, numero_seguimiento: int) -> dict:
    """
    Genera mensaje de seguimiento para una venta con Llama 3.1.
    Retorna dict con: mensaje, _tokens.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Eres un experto en seguimiento de ventas. "
                "Genera mensajes de follow-up profesionales y no agresivos. "
                "SIEMPRE responde UNICAMENTE con JSON valido."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Genera un mensaje de seguimiento #{numero_seguimiento}:\n\n"
                f"PRODUCTO: {producto_nombre}\n"
                f"MENSAJE ANTERIOR: {mensaje_anterior[:300]}\n"
                f"RESPUESTA DEL LEAD: {respuesta_lead or 'Sin respuesta'}\n\n"
                f"Responde SOLO con JSON:\n"
                f'{{\n'
                f'  "mensaje": "Texto del seguimiento",\n'
                f'  "tono": "amigable|urgente|informativo"\n'
                f'}}'
            ),
        },
    ]

    result = await _call_groq(messages, temperature=0.6)

    if "error" in result:
        return {"mensaje": f"Hola, queria hacer seguimiento sobre {producto_nombre}.", **result}

    try:
        parsed = extract_json(result["_raw"])
        parsed["_tokens"] = result["_tokens"]
        parsed["_motor"] = result["_motor"]
        return parsed
    except (ValueError, KeyError) as e:
        logger.error(f"generar_seguimiento parse error: {e}")
        return {
            "mensaje": f"Hola, queria hacer seguimiento sobre {producto_nombre}.",
            "_tokens": result.get("_tokens", 0),
            "_motor": "LLAMA",
        }


async def chat_libre(mensaje: str) -> dict:
    """
    Chat libre con la IA (Llama 3.1).
    Retorna dict con: text, _motor, _tokens.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Eres Tico, el asistente IA de TicoViz Corporation. "
                "Eres util, profesional y conciso. "
                "Puedes ayudar con preguntas sobre tecnologia, negocios, productos digitales, etc. "
                "Responde en texto plano, sin JSON."
            ),
        },
        {
            "role": "user",
            "content": mensaje,
        },
    ]

    result = await _call_groq(messages, temperature=0.7)

    if "error" in result:
        return {"text": f"Error: {result['error']}", "_motor": "LLAMA", "_tokens": 0}

    return {
        "text": result.get("_raw", "Sin respuesta"),
        "respuesta": result.get("_raw", "Sin respuesta"),
        "_motor": result["_motor"],
        "_tokens": result["_tokens"],
    }
