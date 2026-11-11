"""Agente de análisis (LLM 1): clasifica la pregunta y extrae parámetros. Salida JSON validada con Pydantic."""
import re
import time
import unicodedata

from pydantic import ValidationError

from agentes.esquemas import Analisis, Parametros, Tema
from app import config, llm, prompts

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def tiene_palabra_sensible(texto: str) -> bool:
    t = sin_tildes(texto)
    return any(sin_tildes(p) in t for p in config.PALABRAS_SENSIBLES)


def _analizar_mock(mensaje: str) -> Analisis:
    """Clasificador simulado por palabras clave (solo para desarrollo sin API)."""
    t = sin_tildes(mensaje)
    if tiene_palabra_sensible(t) or "cesantia" in t:
        tema, riesgo = Tema.despido, "alto"
    else:
        riesgo = "bajo"
        if "aguinaldo" in t:
            tema = Tema.aguinaldo
        elif any(p in t for p in ("ccss", "cargas", "patronal", "planilla", "seguro social")):
            tema = Tema.ccss
        elif any(p in t for p in ("hacienda", "tribu", "renta", "iva")):
            tema = Tema.hacienda
        elif any(p in t for p in ("ins ", "riesgos del trabajo", "poliza")):
            tema = Tema.ins
        else:
            tema = Tema.otro

    # Salario: primer número de 5+ dígitos (con espacios/puntos como separador de miles)
    salario = None
    m = re.search(r"₡?\s?(\d{1,3}(?:[ .,]\d{3})+|\d{5,})", mensaje)
    if m:
        salario = float(re.sub(r"\D", "", m.group(1)))

    fecha_ingreso = None
    mes = next((n for nombre, n in _MESES.items() if re.search(rf"\b{nombre}\b", t)), None)
    if mes and any(p in t for p in ("entro", "ingreso", "empezo", "comenzo", "inicio")):
        fecha_ingreso = f"2026-{mes:02d}-01"

    n_emp = None
    m = re.search(r"(\d+)\s+(?:empleados|trabajadores|colaboradores)", t)
    if m:
        n_emp = int(m.group(1))

    requiere = bool(salario) or any(p in t for p in ("cuanto", "calcul", "monto"))
    intencion = "calculo" if requiere else ("tramite" if any(p in t for p in ("como hago", "tramite", "inscrib")) else "info")
    return Analisis(
        tema=tema, intencion=intencion, riesgo=riesgo, requiere_calculo=requiere,
        parametros=Parametros(salario_mensual=salario, fecha_ingreso=fecha_ingreso, fecha_salida=None, n_empleados=n_emp),
    )


def analizar(mensaje_enmascarado: str, limite: float) -> tuple[Analisis, int, int]:
    """Devuelve (analisis, tokens_in, tokens_out). Con modo mock no gasta API."""
    if llm.modo_mock():
        return _analizar_mock(mensaje_enmascarado), 0, 0

    system, _ = prompts.cargar("analisis")
    cfg = llm.config_base(system, config.MAX_TOKENS_ANALISIS)
    cfg.response_mime_type = "application/json"
    cfg.response_schema = Analisis
    contenido = f"<pregunta>{mensaje_enmascarado}</pregunta>"

    for intento in range(2):
        resp = llm.generar(llm.modelos()[0], contenido, cfg, limite)
        t_in, t_out = llm.tokens(resp)
        try:
            return Analisis.model_validate_json(resp.text), t_in, t_out
        except (ValidationError, ValueError, TypeError):
            if intento == 1 or limite - time.monotonic() < 3:
                raise llm.LLMNoDisponible("El análisis no devolvió un JSON válido")
    raise llm.LLMNoDisponible("El análisis no devolvió un JSON válido")
