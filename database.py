"""
TicoViz Corporation v2 — Base de Datos
SQLite con FTS5 para busqueda de conocimiento (MP5).
"""
import sqlite3
import logging
from typing import List, Optional
from datetime import datetime
from models import Product, Lead, Sale, KnowledgeEntry, QAReport, SystemStats
from config import DATABASE_PATH

logger = logging.getLogger("ticoviz.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    """Crea todas las tablas si no existen."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                descripcion TEXT DEFAULT '',
                idea_original TEXT DEFAULT '',
                codigo TEXT DEFAULT '',
                analisis_ia TEXT DEFAULT '',
                precio_sugerido REAL DEFAULT 0.0,
                moneda TEXT DEFAULT 'USD',
                categoria TEXT DEFAULT '',
                tecnologias TEXT DEFAULT '',
                pdf_path TEXT DEFAULT '',
                pptx_path TEXT DEFAULT '',
                xlsx_path TEXT DEFAULT '',
                status TEXT DEFAULT 'idea',
                motor_usado TEXT DEFAULT '',
                tokens_consumidos INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                contacto TEXT DEFAULT '',
                plataforma TEXT DEFAULT '',
                necesidad TEXT DEFAULT '',
                presupuesto_estimado REAL DEFAULT 0.0,
                score INTEGER DEFAULT 0,
                url TEXT DEFAULT '',
                notas TEXT DEFAULT '',
                producto_id INTEGER,
                status TEXT DEFAULT 'nuevo',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (producto_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                lead_id INTEGER NOT NULL,
                mensaje_enviado TEXT DEFAULT '',
                respuesta TEXT DEFAULT '',
                precio_ofrecido REAL DEFAULT 0.0,
                precio_final REAL DEFAULT 0.0,
                seguimientos INTEGER DEFAULT 0,
                proximo_seguimiento TEXT DEFAULT '',
                objeciones TEXT DEFAULT '',
                status TEXT DEFAULT 'pendiente',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT DEFAULT 'general',
                titulo TEXT NOT NULL,
                contenido TEXT DEFAULT '',
                fuente TEXT DEFAULT 'sistema',
                relevancia REAL DEFAULT 0.5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS qa_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                tipo_check TEXT DEFAULT '',
                passed INTEGER DEFAULT 0,
                score INTEGER DEFAULT 0,
                detalles TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (producto_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                departamento TEXT NOT NULL,
                accion TEXT NOT NULL,
                detalle TEXT DEFAULT '',
                motor TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                motor TEXT NOT NULL,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                funcion TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # FTS5 para busqueda semantica en knowledge
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(titulo, contenido, categoria, content=knowledge, content_rowid=id)
            """)
        except Exception:
            pass  # FTS5 ya existe o no soportado
        conn.commit()
        logger.info("Base de datos inicializada")
    except Exception as e:
        logger.error(f"Error inicializando DB: {e}")
    finally:
        conn.close()


# ==================== PRODUCTS ====================

def save_product(product: Product) -> int:
    conn = get_connection()
    try:
        if product.id:
            conn.execute("""
                UPDATE products SET nombre=?, descripcion=?, idea_original=?,
                codigo=?, analisis_ia=?, precio_sugerido=?, moneda=?, categoria=?,
                tecnologias=?, pdf_path=?, pptx_path=?, xlsx_path=?, status=?,
                motor_usado=?, tokens_consumidos=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (product.nombre, product.descripcion, product.idea_original,
                  product.codigo, product.analisis_ia, product.precio_sugerido,
                  product.moneda, product.categoria, product.tecnologias,
                  product.pdf_path, product.pptx_path, product.xlsx_path,
                  product.status, product.motor_usado, product.tokens_consumidos,
                  product.id))
            conn.commit()
            return product.id
        else:
            cursor = conn.execute("""
                INSERT INTO products (nombre, descripcion, idea_original, codigo,
                analisis_ia, precio_sugerido, moneda, categoria, tecnologias,
                pdf_path, pptx_path, xlsx_path, status, motor_usado, tokens_consumidos)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (product.nombre, product.descripcion, product.idea_original,
                  product.codigo, product.analisis_ia, product.precio_sugerido,
                  product.moneda, product.categoria, product.tecnologias,
                  product.pdf_path, product.pptx_path, product.xlsx_path,
                  product.status, product.motor_usado, product.tokens_consumidos))
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def get_product(product_id: int) -> Optional[Product]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not row:
            return None
        return Product(**{k: row[k] for k in row.keys()})
    finally:
        conn.close()


def list_products(limit: int = 50) -> List[Product]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Product(**{k: r[k] for k in r.keys()}) for r in rows]
    finally:
        conn.close()


# ==================== LEADS ====================

def save_lead(lead: Lead) -> int:
    conn = get_connection()
    try:
        if lead.id:
            conn.execute("""
                UPDATE leads SET nombre=?, contacto=?, plataforma=?, necesidad=?,
                presupuesto_estimado=?, score=?, url=?, notas=?, producto_id=?, status=?
                WHERE id=?
            """, (lead.nombre, lead.contacto, lead.plataforma, lead.necesidad,
                  lead.presupuesto_estimado, lead.score, lead.url, lead.notas,
                  lead.producto_id, lead.status, lead.id))
            conn.commit()
            return lead.id
        else:
            cursor = conn.execute("""
                INSERT INTO leads (nombre, contacto, plataforma, necesidad,
                presupuesto_estimado, score, url, notas, producto_id, status)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (lead.nombre, lead.contacto, lead.plataforma, lead.necesidad,
                  lead.presupuesto_estimado, lead.score, lead.url, lead.notas,
                  lead.producto_id, lead.status))
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def get_lead(lead_id: int) -> Optional[Lead]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            return None
        return Lead(**{k: row[k] for k in row.keys()})
    finally:
        conn.close()


def list_leads(limit: int = 50) -> List[Lead]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY score DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Lead(**{k: r[k] for k in r.keys()}) for r in rows]
    finally:
        conn.close()


# ==================== SALES ====================

def save_sale(sale: Sale) -> int:
    conn = get_connection()
    try:
        if sale.id:
            conn.execute("""
                UPDATE sales SET product_id=?, lead_id=?, mensaje_enviado=?,
                respuesta=?, precio_ofrecido=?, precio_final=?, seguimientos=?,
                proximo_seguimiento=?, objeciones=?, status=?
                WHERE id=?
            """, (sale.product_id, sale.lead_id, sale.mensaje_enviado,
                  sale.respuesta, sale.precio_ofrecido, sale.precio_final,
                  sale.seguimientos, sale.proximo_seguimiento, sale.objeciones,
                  sale.status, sale.id))
            conn.commit()
            return sale.id
        else:
            cursor = conn.execute("""
                INSERT INTO sales (product_id, lead_id, mensaje_enviado, respuesta,
                precio_ofrecido, precio_final, seguimientos, proximo_seguimiento,
                objeciones, status)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (sale.product_id, sale.lead_id, sale.mensaje_enviado,
                  sale.respuesta, sale.precio_ofrecido, sale.precio_final,
                  sale.seguimientos, sale.proximo_seguimiento, sale.objeciones,
                  sale.status))
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def list_sales(limit: int = 50) -> List[Sale]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM sales ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Sale(**{k: r[k] for k in r.keys()}) for r in rows]
    finally:
        conn.close()


# ==================== KNOWLEDGE (MP5) ====================

def save_knowledge(entry: KnowledgeEntry) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO knowledge (categoria, titulo, contenido, fuente, relevancia)
            VALUES (?,?,?,?,?)
        """, (entry.categoria, entry.titulo, entry.contenido,
              entry.fuente, entry.relevancia))
        kid = cursor.lastrowid
        # Actualizar FTS5
        try:
            conn.execute("""
                INSERT INTO knowledge_fts(rowid, titulo, contenido, categoria)
                VALUES (?,?,?,?)
            """, (kid, entry.titulo, entry.contenido, entry.categoria))
        except Exception:
            pass
        conn.commit()
        return kid
    finally:
        conn.close()


def search_knowledge(query: str, limit: int = 5) -> List[KnowledgeEntry]:
    conn = get_connection()
    try:
        try:
            rows = conn.execute("""
                SELECT k.* FROM knowledge k
                JOIN knowledge_fts fts ON k.id = fts.rowid
                WHERE knowledge_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (query, limit)).fetchall()
        except Exception:
            rows = conn.execute("""
                SELECT * FROM knowledge
                WHERE titulo LIKE ? OR contenido LIKE ?
                ORDER BY relevancia DESC LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit)).fetchall()
        return [KnowledgeEntry(**{k: r[k] for k in r.keys()}) for r in rows]
    finally:
        conn.close()


# ==================== QA REPORTS ====================

def save_qa_report(report: QAReport) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO qa_reports (producto_id, tipo_check, passed, score, detalles)
            VALUES (?,?,?,?,?)
        """, (report.producto_id, report.tipo_check, int(report.passed),
              report.score, report.detalles))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ==================== ACTIVITY LOG ====================

def log_activity(departamento: str, accion: str, detalle: str = "",
                 motor: str = ""):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO activity_log (departamento, accion, detalle, motor)
            VALUES (?,?,?,?)
        """, (departamento, accion, detalle, motor))
        conn.commit()
    except Exception as e:
        logger.error(f"Error logging activity: {e}")
    finally:
        conn.close()


def get_recent_activity(limit: int = 10) -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ==================== TOKEN USAGE ====================

def log_tokens(motor: str, tokens_in: int, tokens_out: int, funcion: str = ""):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO token_usage (motor, tokens_in, tokens_out, funcion)
            VALUES (?,?,?,?)
        """, (motor, tokens_in, tokens_out, funcion))
        conn.commit()
    except Exception as e:
        logger.error(f"Error logging tokens: {e}")
    finally:
        conn.close()


# ==================== STATS ====================

def get_stats() -> SystemStats:
    conn = get_connection()
    try:
        stats = SystemStats()
        r = conn.execute("SELECT COUNT(*) as c FROM products").fetchone()
        stats.productos_total = r["c"] if r else 0
        r = conn.execute(
            "SELECT COUNT(*) as c FROM products WHERE status='listo'"
        ).fetchone()
        stats.productos_listos = r["c"] if r else 0
        r = conn.execute(
            "SELECT COUNT(*) as c FROM products WHERE status='vendido'"
        ).fetchone()
        stats.productos_vendidos = r["c"] if r else 0
        r = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()
        stats.leads_total = r["c"] if r else 0
        r = conn.execute(
            "SELECT COUNT(*) as c FROM leads WHERE status NOT IN ('cerrado','descartado')"
        ).fetchone()
        stats.leads_activos = r["c"] if r else 0
        r = conn.execute("SELECT COUNT(*) as c FROM sales").fetchone()
        stats.ventas_total = r["c"] if r else 0
        r = conn.execute(
            "SELECT COUNT(*) as c FROM sales WHERE status='cerrada'"
        ).fetchone()
        stats.ventas_cerradas = r["c"] if r else 0
        r = conn.execute(
            "SELECT COALESCE(SUM(precio_final),0) as t FROM sales WHERE status='cerrada'"
        ).fetchone()
        stats.ingresos_total = r["t"] if r else 0.0
        r = conn.execute(
            "SELECT COALESCE(SUM(tokens_in+tokens_out),0) as t FROM token_usage"
        ).fetchone()
        stats.tokens_total = r["t"] if r else 0
        return stats
    finally:
        conn.close()
