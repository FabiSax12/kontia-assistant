"""Agente de recepción (sin LLM): enmascara datos personales y limita el largo del mensaje."""
import re

from app import config

# El orden importa: lo más específico primero para que un patrón no se coma al otro.
_PATRONES: list[tuple[str, re.Pattern]] = [
    ("[CORREO]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # IBAN CR: CR + 20 dígitos, con o sin espacios (ej. CR05 0152 0200 1026 2840 66)
    ("[IBAN]", re.compile(r"\bCR(?:[ -]?\d){20}\b", re.IGNORECASE)),
    # Cédula jurídica: 3-101-123456 (3, 3 dígitos, 6 dígitos), con guiones, espacios o pegado
    ("[CEDULA_JURIDICA]", re.compile(r"(?<!\d)3[ -]?\d{3}[ -]?\d{6}(?!\d)")),
    # DIMEX: 11 o 12 dígitos seguidos
    ("[DIMEX]", re.compile(r"(?<![\d₡])\d{11,12}(?!\d)")),
    # Cédula física: 9 dígitos, ej. 1-1234-0567, 1 1234 0567, 112340567
    ("[CEDULA]", re.compile(r"(?<![\d₡])\d[ -]?\d{4}[ -]?\d{4}(?!\d)")),
    # Teléfono CR: 8 dígitos, con o sin +506 / 506; admite 8888-8888 y 8888 8888
    ("[TELEFONO]", re.compile(r"(?<![\d₡])(?:\+?506[ -]?)?\d{4}[ -]?\d{4}(?!\d)")),
]

# Un monto precedido por ₡ o "colones" nunca debe tratarse como dato personal.
_MONTO_CON_SIMBOLO = re.compile(r"₡\s?\d[\d  .,]*|\d[\d  .,]*\s?colones", re.IGNORECASE)


def enmascarar(texto: str) -> str:
    """Reemplaza PII por etiquetas. No toca montos en colones (₡450 000)."""
    # Protegemos los montos con ₡ sustituyéndolos por marcadores y los restauramos al final.
    protegidos: list[str] = []

    def _proteger(m: re.Match) -> str:
        protegidos.append(m.group(0))
        return f"\x00{len(protegidos) - 1}\x00"

    resultado = _MONTO_CON_SIMBOLO.sub(_proteger, texto)
    for etiqueta, patron in _PATRONES:
        resultado = patron.sub(etiqueta, resultado)
    return re.sub(r"\x00(\d+)\x00", lambda m: protegidos[int(m.group(1))], resultado)


def recibir(mensaje: str) -> str:
    """Limita a 800 caracteres y enmascara. Devuelve el texto seguro para el LLM y la base."""
    return enmascarar(mensaje.strip()[: config.MAX_CARACTERES_MENSAJE])
