"""Cliente de Gemini (google-genai): elección de modelos, reintentos con backoff y conteo de tokens.

Sin GEMINI_API_KEY el sistema entra en MODO MOCK: los agentes usan clasificador y respuesta simulados.
"""
import re
import time
from functools import lru_cache

from google import genai
from google.genai import errors, types

from app import config


# Modelos que rechazaron thinking_budget=0 (400): no se vuelve a enviar para no gastar cuota en el reintento.
_sin_thinking: set[str] = set()


class LLMNoDisponible(Exception):
    """Se agotaron los reintentos, el tiempo o la API falló de forma no recuperable."""


def modo_mock() -> bool:
    return not config.GEMINI_API_KEY


@lru_cache(maxsize=1)
def cliente() -> genai.Client:
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _version_modelo(nombre: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", nombre)
    return float(m.group(1)) if m else 0.0


def _elegir(disponibles: list[str], lite: bool) -> str | None:
    """Elige el Flash-Lite o el Flash estable más reciente (evita preview, tts, imagen, etc.)."""
    excluir = ("tts", "image", "live", "audio", "thinking", "exp", "embedding", "robotics", "computer", "preview")
    candidatos = []
    for n in disponibles:
        corto = n.removeprefix("models/")
        if "flash" not in corto or any(x in corto for x in excluir):
            continue
        if ("lite" in corto) != lite:
            continue
        # "-latest" y "-001" no se descartan, pero se prefiere el nombre más corto de la misma versión
        candidatos.append((_version_modelo(corto), -len(corto), corto))
    return max(candidatos)[2] if candidatos else None


@lru_cache(maxsize=1)
def modelos() -> tuple[str, str]:
    """(modelo_analisis, modelo_respuesta). Respeta las variables de entorno; si no, consulta models.list()."""
    analisis, respuesta = config.MODELO_ANALISIS, config.MODELO_RESPUESTA
    if analisis and respuesta:
        return analisis, respuesta
    try:
        disponibles = [
            m.name for m in cliente().models.list()
            if "generateContent" in (m.supported_actions or [])
        ]
    except Exception as e:  # noqa: BLE001
        raise LLMNoDisponible(f"No pude listar modelos de Gemini: {e}") from e
    analisis = analisis or _elegir(disponibles, lite=True) or _elegir(disponibles, lite=False)
    respuesta = respuesta or _elegir(disponibles, lite=False)
    if not analisis or not respuesta:
        raise LLMNoDisponible("No encontré modelos Flash/Flash-Lite disponibles. Definí MODELO_ANALISIS y MODELO_RESPUESTA.")
    return analisis, respuesta


def _es_reintentable(e: Exception) -> bool:
    return isinstance(e, errors.APIError) and getattr(e, "code", None) in (429, 503)


def cuota_diaria_agotada(e: Exception) -> bool:
    """429 por cuota diaria (RPD): reintentar no sirve, la cuota vuelve en horas."""
    return isinstance(e, errors.APIError) and getattr(e, "code", None) == 429 and "PerDay" in str(e)


def generar(modelo: str, contenidos, configuracion: types.GenerateContentConfig, limite: float):
    """generate_content con backoff exponencial ante 429/503 (máx. 2 reintentos) dentro del límite de tiempo.

    'limite' es un instante de time.monotonic(). Lanza LLMNoDisponible si no se logra a tiempo.
    """
    intento = 0
    quitar_thinking = modelo in _sin_thinking
    while True:
        restante = limite - time.monotonic()
        if restante <= 0.5:
            raise LLMNoDisponible("Tiempo agotado antes de llamar a Gemini")
        cfg = configuracion.model_copy(deep=True)
        cfg.http_options = types.HttpOptions(timeout=int(restante * 1000))
        if quitar_thinking:
            cfg.thinking_config = None
        try:
            return cliente().models.generate_content(model=modelo, contents=contenidos, config=cfg)
        except Exception as e:  # noqa: BLE001
            if (
                isinstance(e, errors.APIError)
                and getattr(e, "code", None) == 400
                and cfg.thinking_config is not None
                and not quitar_thinking
            ):
                quitar_thinking = True  # el modelo no admite thinking_budget=0: reintenta sin eso
                _sin_thinking.add(modelo)
                continue
            if cuota_diaria_agotada(e):
                raise LLMNoDisponible(f"Cuota diaria de Gemini agotada para {modelo}") from e
            if _es_reintentable(e) and intento < config.MAX_REINTENTOS_API:
                espera = 2**intento * 0.8
                intento += 1
                if limite - time.monotonic() <= espera + 1:
                    raise LLMNoDisponible("Gemini saturado y sin tiempo para reintentar") from e
                time.sleep(espera)
                continue
            raise LLMNoDisponible(f"Fallo de Gemini: {e}") from e


def tokens(respuesta) -> tuple[int, int]:
    """(entrada, salida) desde usage_metadata; la salida incluye tokens de razonamiento."""
    u = getattr(respuesta, "usage_metadata", None)
    if u is None:
        return 0, 0
    entrada = (u.prompt_token_count or 0) + (u.tool_use_prompt_token_count or 0)
    salida = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
    return entrada, salida


def costo_usd(tokens_in: int, tokens_out: int) -> float:
    """0 en el tier gratuito; con USAR_TIER_GRATUITO=False estima con los precios del tier pago."""
    if config.USAR_TIER_GRATUITO:
        return 0.0
    return (
        tokens_in * config.PRECIO_USD_MILLON_ENTRADA + tokens_out * config.PRECIO_USD_MILLON_SALIDA
    ) / 1_000_000


def config_base(system: str, max_tokens: int) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system,
        temperature=config.TEMPERATURA,
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def declaraciones_tools(esquemas: list[dict]) -> list[types.Tool]:
    """Convierte los esquemas de las calculadoras en declaraciones de function calling de Gemini."""
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=e["name"], description=e["description"], parameters_json_schema=e["parameters"]
                )
                for e in esquemas
            ]
        )
    ]
