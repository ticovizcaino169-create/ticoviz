"""
TicoViz Corporation v2 — Modelos de Datos
Estructuras para productos, leads, ventas y conocimiento.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class ProductStatus(Enum):
    IDEA = "idea"
    EN_DESARROLLO = "en_desarrollo"
    LISTO = "listo"
    EN_VENTA = "en_venta"
    VENDIDO = "vendido"


class LeadStatus(Enum):
    NUEVO = "nuevo"
    CONTACTADO = "contactado"
    INTERESADO = "interesado"
    NEGOCIANDO = "negociando"
    CERRADO = "cerrado"
    DESCARTADO = "descartado"


class SaleStatus(Enum):
    PENDIENTE = "pendiente"
    MENSAJE_ENVIADO = "mensaje_enviado"
    SEGUIMIENTO = "seguimiento"
    NEGOCIANDO = "negociando"
    CERRADA = "cerrada"
    PERDIDA = "perdida"


class MotorID(Enum):
    NV8 = "NV8"
    LLAMA = "LLAMA"
    GEMINI = "GEMINI"
    MP4 = "MP4"
    MP5 = "MP5"
    MP8 = "MP8"


@dataclass
class Product:
    id: Optional[int] = None
    nombre: str = ""
    descripcion: str = ""
    idea_original: str = ""
    codigo: str = ""
    analisis_ia: str = ""
    precio_sugerido: float = 0.0
    moneda: str = "USD"
    categoria: str = ""
    tecnologias: str = ""
    pdf_path: str = ""
    pptx_path: str = ""
    xlsx_path: str = ""
    status: str = ProductStatus.IDEA.value
    motor_usado: str = ""
    tokens_consumidos: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Lead:
    id: Optional[int] = None
    nombre: str = ""
    contacto: str = ""
    plataforma: str = ""
    necesidad: str = ""
    presupuesto_estimado: float = 0.0
    score: int = 0
    url: str = ""
    notas: str = ""
    producto_id: Optional[int] = None
    status: str = LeadStatus.NUEVO.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Sale:
    id: Optional[int] = None
    product_id: int = 0
    lead_id: int = 0
    mensaje_enviado: str = ""
    respuesta: str = ""
    precio_ofrecido: float = 0.0
    precio_final: float = 0.0
    seguimientos: int = 0
    proximo_seguimiento: str = ""
    objeciones: str = ""
    status: str = SaleStatus.PENDIENTE.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class KnowledgeEntry:
    id: Optional[int] = None
    categoria: str = ""
    titulo: str = ""
    contenido: str = ""
    fuente: str = ""
    relevancia: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class QAReport:
    id: Optional[int] = None
    producto_id: int = 0
    tipo_check: str = ""
    passed: bool = False
    score: int = 0
    detalles: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SystemStats:
    productos_total: int = 0
    productos_listos: int = 0
    productos_vendidos: int = 0
    leads_total: int = 0
    leads_activos: int = 0
    ventas_total: int = 0
    ventas_cerradas: int = 0
    ingresos_total: float = 0.0
    tokens_total: int = 0
