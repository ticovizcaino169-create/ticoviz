"""
TicoViz Corporation v2 — MP8: QA & Debugging Agent
Control de calidad automatizado para codigo y productos.
Usa Gemini para analisis de codigo, verifica sintaxis local.
"""
import logging
import ast
import re
from typing import Optional

import ai_engine
import database as db
from models import QAReport

logger = logging.getLogger("ticoviz.mp8")


class QAAgent:
    """MP8 — Agente de Control de Calidad y Debugging."""

    def __init__(self):
        logger.info("MP8 QA Agent inicializado")

    async def verificar_producto(self, producto_id: int, codigo: str,
                                  notify_callback=None) -> dict:
        """
        Verificacion completa de un producto:
        1. Sintaxis Python
        2. Estructura del codigo
        3. Analisis de seguridad
        4. Analisis IA del codigo (Gemini)
        5. Reporte final
        """
        resultados = {
            "producto_id": producto_id,
            "checks": [],
            "score_total": 0,
            "aprobado": False,
        }

        async def notificar(msg):
            logger.info(msg)
            if notify_callback:
                await notify_callback(msg)

        # CHECK 1: Sintaxis Python
        await notificar("MP8: Verificando sintaxis Python...")
        check_syntax = self._verificar_sintaxis(codigo)
        resultados["checks"].append(check_syntax)
        self._guardar_reporte(producto_id, check_syntax)

        if not check_syntax["passed"]:
            await notificar(f"MP8: Error de sintaxis: {check_syntax['detalles']}")
            resultados["score_total"] = 10
            return resultados

        await notificar("MP8: Sintaxis correcta")

        # CHECK 2: Estructura del codigo
        await notificar("MP8: Verificando estructura...")
        check_structure = self._verificar_estructura(codigo)
        resultados["checks"].append(check_structure)
        self._guardar_reporte(producto_id, check_structure)
        status = "OK" if check_structure["passed"] else "WARN"
        await notificar(f"MP8: Estructura — {status} — {check_structure['resumen']}")

        # CHECK 3: Seguridad
        await notificar("MP8: Verificando seguridad...")
        check_security = self._verificar_seguridad(codigo)
        resultados["checks"].append(check_security)
        self._guardar_reporte(producto_id, check_security)
        status = "OK" if check_security["passed"] else "WARN"
        await notificar(f"MP8: Seguridad — {status} — {check_security['resumen']}")

        # CHECK 4: Analisis IA (Gemini)
        await notificar("MP8: Analisis de calidad con IA...")
        try:
            check_ia = await ai_engine.verificar_codigo(codigo)
            ia_report = {
                "tipo": "ia_quality",
                "passed": check_ia.get("calidad", 0) >= 6,
                "score": check_ia.get("calidad", 5) * 10,
                "detalles": check_ia.get("resumen", ""),
                "resumen": f"Calidad IA: {check_ia.get('calidad', '?')}/10",
                "errores": check_ia.get("errores", []),
                "sugerencias": check_ia.get("sugerencias", []),
            }
            resultados["checks"].append(ia_report)
            self._guardar_reporte(producto_id, ia_report)

            tokens = check_ia.get("_tokens", 0)
            if tokens:
                db.log_tokens("GEMINI", tokens // 2, tokens // 2, "qa_code_review")

            await notificar(f"MP8: Calidad IA — {ia_report['resumen']}")
        except Exception as e:
            logger.error(f"MP8: Error en analisis IA: {e}")
            await notificar(f"MP8: Analisis IA fallo, continuando sin el...")

        # Calcular score total
        scores = [c.get("score", 50) for c in resultados["checks"]]
        resultados["score_total"] = sum(scores) // len(scores) if scores else 0
        resultados["aprobado"] = resultados["score_total"] >= 60

        # Log
        estado = "APROBADO" if resultados["aprobado"] else "RECHAZADO"
        await notificar(
            f"MP8: Verificacion completa — {estado} "
            f"(Score: {resultados['score_total']}/100)"
        )
        db.log_activity("qa", "verificacion", f"Producto #{producto_id}: {estado}", motor="MP8")

        return resultados

    def _verificar_sintaxis(self, codigo: str) -> dict:
        """Verifica sintaxis Python con ast.parse."""
        try:
            ast.parse(codigo)
            return {
                "tipo": "sintaxis",
                "passed": True,
                "score": 100,
                "detalles": "Sintaxis Python valida",
                "resumen": "Sintaxis OK",
            }
        except SyntaxError as e:
            return {
                "tipo": "sintaxis",
                "passed": False,
                "score": 0,
                "detalles": f"Linea {e.lineno}: {e.msg}",
                "resumen": f"Error sintaxis linea {e.lineno}",
            }

    def _verificar_estructura(self, codigo: str) -> dict:
        """Analiza estructura del codigo: clases, funciones, imports, etc."""
        try:
            tree = ast.parse(codigo)
        except SyntaxError:
            return {
                "tipo": "estructura",
                "passed": False,
                "score": 0,
                "detalles": "No se puede analizar (error de sintaxis)",
                "resumen": "Error de sintaxis",
            }

        clases = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        funciones = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]

        lineas = codigo.count("\n") + 1
        tiene_docstrings = any(
            isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
            for n in clases + funciones
            if n.body
        )

        score = 50
        detalles = []

        if len(funciones) > 0:
            score += 10
            detalles.append(f"{len(funciones)} funciones")
        if len(clases) > 0:
            score += 10
            detalles.append(f"{len(clases)} clases")
        if len(imports) > 0:
            score += 5
            detalles.append(f"{len(imports)} imports")
        if tiene_docstrings:
            score += 15
            detalles.append("Tiene docstrings")
        if lineas > 50:
            score += 10
            detalles.append(f"{lineas} lineas")

        return {
            "tipo": "estructura",
            "passed": score >= 60,
            "score": min(score, 100),
            "detalles": ", ".join(detalles) if detalles else "Codigo basico",
            "resumen": f"{len(funciones)} func, {len(clases)} cls, {lineas} lineas",
        }

    def _verificar_seguridad(self, codigo: str) -> dict:
        """Busca patrones de seguridad peligrosos."""
        problemas = []

        patrones_peligrosos = [
            (r"eval\s*\(", "eval() encontrado — riesgo de ejecucion arbitraria"),
            (r"exec\s*\(", "exec() encontrado — riesgo de ejecucion arbitraria"),
            (r"__import__\s*\(", "__import__() dinamico encontrado"),
            (r"subprocess\.\w+\(.*shell\s*=\s*True", "subprocess con shell=True"),
            (r"os\.system\s*\(", "os.system() — usar subprocess mejor"),
            (r"pickle\.loads?\s*\(", "pickle — riesgo de deserializacion insegura"),
            (r"password\s*=\s*['\"][^'\"]+['\"]", "Password hardcodeado"),
            (r"api_key\s*=\s*['\"][^'\"]+['\"]", "API key hardcodeada"),
        ]

        for patron, desc in patrones_peligrosos:
            matches = re.findall(patron, codigo, re.IGNORECASE)
            if matches:
                problemas.append(desc)

        if not problemas:
            return {
                "tipo": "seguridad",
                "passed": True,
                "score": 100,
                "detalles": "Sin problemas de seguridad detectados",
                "resumen": "Seguridad OK",
            }

        score = max(100 - (len(problemas) * 20), 10)
        return {
            "tipo": "seguridad",
            "passed": score >= 60,
            "score": score,
            "detalles": "; ".join(problemas),
            "resumen": f"{len(problemas)} problema(s) de seguridad",
        }

    def _guardar_reporte(self, producto_id: int, check: dict):
        """Guarda reporte de QA en la base de datos."""
        try:
            report = QAReport(
                producto_id=producto_id,
                tipo_check=check.get("tipo", ""),
                resultado="pass" if check.get("passed") else "fail",
                score=check.get("score", 0),
                detalles=check.get("detalles", ""),
                sugerencias="; ".join(check.get("sugerencias", [])),
            )
            db.save_qa_report(report)
        except Exception as e:
            logger.error(f"MP8: Error guardando reporte: {e}")
