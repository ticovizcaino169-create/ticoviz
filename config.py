"""
TicoViz Corporation v2 — Configuracion Central
Adaptado para Railway (PORT dinamico + Volume persistente)
Motores: NV8 + Llama 3.1 (Groq) + Gemini Flash + MP4 + MP5 + MP8
Portal Web + Pagos Crypto
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Rutas ---
BASE_DIR = Path(__file__).parent
_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
DATA_DIR = Path(_volume) if _volume else BASE_DIR
PRODUCTS_DIR = DATA_DIR / os.getenv("PRODUCTS_DIR", "products")
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

# --- Groq API (Llama 3.1) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")


# --- Gemini API (Flash) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# --- Base de datos (en volume para persistencia) ---
DATABASE_PATH = DATA_DIR / os.getenv("DATABASE_PATH", "ticoviz.db")

# --- Scraper ---
MAX_SCRAPER_RESULTS = int(os.getenv("MAX_SCRAPER_RESULTS", "20"))

# --- Ventas ---
SALES_FOLLOWUP_HOURS = int(os.getenv("SALES_FOLLOWUP_HOURS", "24"))

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Web Portal ---
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "5000")))
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY", "ticoviz-secret-change-me")

# --- Crypto Payments ---
CRYPTO_WALLETS = {
    "USDT_TRC20": os.getenv("CRYPTO_USDT_TRC20", ""),
    "BTC": os.getenv("CRYPTO_BTC", ""),
    "ETH": os.getenv("CRYPTO_ETH", ""),
}

# --- Motores del sistema ---
MOTORES = {
    "NV8":    "Orquestador de Agentes",
    "LLAMA":  "Reasoning Engine (Groq Llama 3.1)",
    "GEMINI": "Execution Engine (Gemini Flash)",
    "MP4":    "Web Scraper & Trend Analyzer",
    "MP5":    "Knowledge Base (SQLite FTS5)",
    "MP8":    "QA & Debugging Agent",
}

# --- Departamentos ---
DEPARTAMENTOS = {
    "rastreo":      "MP4 - Rastreo de Clientes",
    "finanzas":     "Finanzas",
    "marketing":    "Marketing & Estrategia",
    "ventas":       "Ventas",
    "codigo":       "Departamento de Codigo",
    "docs":         "Documentacion",
    "archivos":     "Archivos",
    "motor":        "NV8 - Motor Central",
    "conocimiento": "MP5 - Base de Conocimiento",
    "qa":           "MP8 - Control de Calidad",
    "web":          "Portal Web",
    "pagos":        "Pagos Crypto",
}

# --- Categorias de productos ---
CATEGORIAS = [
    ("app", "Aplicacion Movil/Web"),
    ("bot", "Bot (Telegram/Discord/WhatsApp)"),
    ("herramienta", "Herramienta/Script"),
    ("juego", "Juego"),
    ("api", "API/Backend"),
    ("template", "Template/Diseno"),
    ("saas", "SaaS/Plataforma"),
    ("automatizacion", "Automatizacion"),
    ("otro", "Otro"),
]
