"""
TicoViz Corporation v2 — MP5: Knowledge Base
Base de conocimiento con busqueda FTS5.
Almacena aprendizajes, patrones de mercado y datos de productos.
"""
import logging
from typing import List, Optional
from datetime import datetime

import database as db
from models import KnowledgeEntry

logger = logging.getLogger("ticoviz.mp5")


class KnowledgeBase:
    """MP5 — Base de conocimiento con busqueda semantica FTS5."""

    def __init__(self):
        logger.info("MP5 Knowledge Base inicializada")

    def aprender(self, titulo: str, contenido: str,
                 categoria: str = "general", fuente: str = "sistema",
                 relevancia: float = 0.5) -> int:
        """
        Almacena nuevo conocimiento en la base.
        Categorias: mercado, tecnologia, ventas, competencia, precios, patron
        """
        entry = KnowledgeEntry(
            titulo=titulo,
            contenido=contenido,
            categoria=categoria,
            fuente=fuente,
            relevancia=relevancia,
        )
        entry_id = db.save_knowledge(entry)
        db.log_activity("conocimiento", "aprender", f"#{entry_id}: {titulo}", motor="MP5")
        logger.info(f"MP5: Nuevo conocimiento #{entry_id}: {titulo}")
        return entry_id

    def buscar(self, query: str, limit: int = 5) -> List[KnowledgeEntry]:
        """Busca conocimiento relevante usando FTS5."""
        results = db.search_knowledge(query, limit)
        logger.info(f"MP5: Busqueda '{query}' -> {len(results)} resultados")
        return results

    def buscar_contexto(self, idea: str) -> str:
        """
        Busca conocimiento relevante y lo formatea como contexto
        para los motores de IA.
        """
        entries = self.buscar(idea, limit=5)
        if not entries:
            return ""

        contexto = "CONOCIMIENTO PREVIO RELEVANTE:\n"
        for e in entries:
            contexto += f"- [{e.categoria}] {e.titulo}: {e.contenido[:200]}\n"
        return contexto

    def aprender_de_producto(self, producto_nombre: str, categoria: str,
                              precio: float, tecnologias: str):
        """Aprende automaticamente de cada producto creado."""
        self.aprender(
            titulo=f"Producto: {producto_nombre}",
            contenido=f"Categoria: {categoria}, Precio: ${precio}, "
                      f"Tecnologias: {tecnologias}",
            categoria="productos",
            fuente="auto",
            relevancia=0.7,
        )

    def aprender_de_venta(self, producto_nombre: str, precio_final: float,
                           lead_plataforma: str, exito: bool):
        """Aprende de cada resultado de venta."""
        resultado = "exitosa" if exito else "fallida"
        self.aprender(
            titulo=f"Venta {resultado}: {producto_nombre}",
            contenido=f"Precio final: ${precio_final}, "
                      f"Plataforma: {lead_plataforma}, "
                      f"Resultado: {resultado}",
            categoria="ventas",
            fuente="auto",
            relevancia=0.8 if exito else 0.6,
        )

    def aprender_de_tendencia(self, tendencia: str, plataforma: str,
                               detalles: str):
        """Registra tendencias detectadas por MP4."""
        self.aprender(
            titulo=f"Tendencia: {tendencia}",
            contenido=f"Plataforma: {plataforma}, Detalles: {detalles}",
            categoria="mercado",
            fuente="MP4",
            relevancia=0.6,
        )

    def obtener_resumen(self) -> dict:
        """Resumen de la base de conocimiento."""
        conn = db.get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
            categorias = conn.execute(
                "SELECT categoria, COUNT(*) as cnt FROM knowledge "
                "GROUP BY categoria ORDER BY cnt DESC"
            ).fetchall()
            recientes = conn.execute(
                "SELECT titulo, categoria FROM knowledge "
                "ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
            return {
                "total_entries": total,
                "categorias": {r["categoria"]: r["cnt"] for r in categorias},
                "recientes": [
                    {"titulo": r["titulo"], "categoria": r["categoria"]}
                    for r in recientes
                ],
            }
        finally:
            conn.close()
