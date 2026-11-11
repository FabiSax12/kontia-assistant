"""Configuración central: tasas legales, umbrales y variables de entorno.

Todas las tasas son editables aquí. Las fuentes están marcadas con su fecha;
la revisión final de cada cifra la hace un contador (ver fichas/).
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATA = RAIZ / "data"
DIR_FICHAS = RAIZ / "fichas"
DIR_PROMPTS = RAIZ / "prompts"
DIR_STATIC = RAIZ / "static"
RUTA_DB = DIR_DATA / "kontia.db"
RUTA_INDICE = DIR_DATA / "indice.npz"
RUTA_FICHAS_JSON = DIR_DATA / "fichas.json"


def _cargar_env() -> None:
    """Lee .env sin dependencias externas (no pisa variables ya definidas)."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


_cargar_env()

# --- Tasas (2026; coinciden con la tabla de cuotas publicada por la CCSS en ccss.sa.cr/patronos) ---
TASA_CCSS_PATRONAL = 0.2683          # CCSS patronal 2026: 26.83 %
TASA_CCSS_PATRONAL_SIN_INA = 0.2533  # 25.33 % si el patrono tiene menos de 5 trabajadores (no paga INA)
UMBRAL_EMPLEADOS_INA = 5             # desde 5 trabajadores se paga INA
TASA_CCSS_OBRERA = 0.1083            # CCSS obrera 2026: 10.83 %
TASA_INS_DEFECTO = 0.02              # INS Riesgos del Trabajo: 2 % por defecto (varía por actividad)

# Aguinaldo: periodo 1 dic año anterior - 30 nov; pago a más tardar el 20 de diciembre; sin cargas sociales.
AGUINALDO_DIA_LIMITE = 20
AGUINALDO_MES_LIMITE = 12

# --- RAG ---
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
UMBRAL_SIMILITUD = float(os.getenv("UMBRAL_SIMILITUD", "0.45"))  # se calibra después con escenarios
TOP_K = 3

# --- LLM (Gemini) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODELO_ANALISIS = os.getenv("MODELO_ANALISIS", "").strip()
MODELO_RESPUESTA = os.getenv("MODELO_RESPUESTA", "").strip()
TEMPERATURA = 0.1
MAX_TOKENS_ANALISIS = 300
MAX_TOKENS_RESPUESTA = 500
TIMEOUT_S = float(os.getenv("TIMEOUT_S", "10"))
MAX_REINTENTOS_API = 2
MAX_CARACTERES_MENSAJE = 800
MAX_PALABRAS_RESPUESTA = 120

# Precios del tier PAGO (USD por millón de tokens). Editables: confirmalos en Google AI Studio.
# En el tier gratuito el costo real es 0.
USAR_TIER_GRATUITO = True
PRECIO_USD_MILLON_ENTRADA = 0.30
PRECIO_USD_MILLON_SALIDA = 2.50

# Contacto de ejemplo del prototipo; no es un correo real.
CONTACTO_HUMANO = "contador@kontia.example"

PALABRAS_SENSIBLES = [
    "despido", "despedir", "despedí", "liquidación", "liquidacion", "cesantía", "cesantia",
    "multa", "sanción", "sancion", "inspección", "inspeccion", "inspector", "embargo", "embargar",
    "demanda", "demandar", "demandó", "demando",
]
