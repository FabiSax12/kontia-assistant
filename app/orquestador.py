"""Orquestador: recepción -> análisis -> reglas de derivación -> RAG -> respuesta -> registro.

Presupuesto total de TIMEOUT_S segundos. Nunca devuelve un error crudo: ante fallos, mensaje amable con contacto humano.
"""
import logging
import time

from agentes import analisis as agente_analisis
from agentes import recepcion, registro, respuesta
from agentes.esquemas import Tema
from app import config, llm, prompts
from app.rag import buscar

log = logging.getLogger("kontia")

MENSAJES_DERIVACION = {
    "caso_sensible": (
        "Este tema es delicado y depende de cada caso, así que no lo respondo yo. Lo mejor es que lo revise un "
        "contador antes de tomar cualquier decisión. Dejanos tu contacto y te escribe una persona."
    ),
    "sin_ficha": (
        "No tengo información verificada sobre esa consulta, y prefiero no inventar. Un contador puede ayudarte "
        "con esto. Dejanos tu contacto y te escribe una persona."
    ),
    "validacion_salida": (
        "No pude confirmar con seguridad la respuesta a tu consulta, así que prefiero que la revise un contador. "
        "Dejanos tu contacto y te escribe una persona."
    ),
    "timeout": (
        "La consulta está tardando más de lo normal y no quise dejarte esperando. Probá de nuevo en un momento, o "
        f"escribile a una persona: {config.CONTACTO_HUMANO}."
    ),
    "error": (
        "Tuvimos un problema para procesar tu consulta. Probá de nuevo en un momento, o escribile a una persona: "
        f"{config.CONTACTO_HUMANO}."
    ),
}


def _derivar(motivo: str) -> dict:
    return {
        "respuesta": f"{MENSAJES_DERIVACION[motivo]}\n\n{config.AVISO_FIJO}",
        "ficha": None, "calculo": None, "siguiente_paso": "Pedir revisión de un contador.",
        "derivado": True, "motivo_derivacion": motivo,
    }


def _procesar(session_id: str, mensaje: str, limite: float, ctx: dict) -> dict:
    """Pipeline principal. 'ctx' acumula lo que se va sabiendo para registrar aunque algo falle."""
    ctx["pregunta"] = recepcion.recibir(mensaje)

    analisis, t_in, t_out = agente_analisis.analizar(ctx["pregunta"], limite)
    ctx.update(tema=analisis.tema.value, intencion=analisis.intencion, riesgo=analisis.riesgo,
               tokens_in=t_in, tokens_out=t_out)

    # Regla de derivación: palabras clave Y clasificación del LLM
    if agente_analisis.tiene_palabra_sensible(ctx["pregunta"]) or analisis.riesgo == "alto" or analisis.tema == Tema.despido:
        return _derivar("caso_sensible")

    fichas = buscar.buscar(ctx["pregunta"], None if analisis.tema == Tema.otro else analisis.tema.value)
    ctx["fichas_ids"] = ",".join(f["id"] for f in fichas)
    ctx["score_top1"] = fichas[0]["score"] if fichas else None
    if not buscar.hay_ficha_suficiente(fichas):
        return _derivar("sin_ficha")
    if fichas[0].get("sensible"):
        return _derivar("caso_sensible")

    try:
        r = respuesta.responder(ctx["pregunta"], fichas, analisis, limite)
    except respuesta.RespuestaInvalida as e:
        log.warning("Respuesta inválida: %s", e)
        return _derivar("validacion_salida")
    ctx["tokens_in"] += r.tokens_in
    ctx["tokens_out"] += r.tokens_out
    ctx["tool_usada"] = r.tool_usada
    if r.sin_ficha:
        return _derivar("sin_ficha")

    return {
        "respuesta": respuesta.armar_mensaje(r.respuesta, r.siguiente_paso, r.ficha),
        "ficha": respuesta.ficha_publica(r.ficha),
        "calculo": {"tool": r.tool_usada, "datos": r.calculo} if r.calculo else None,
        "siguiente_paso": r.siguiente_paso, "derivado": False, "motivo_derivacion": None,
    }


def atender(session_id: str, mensaje: str) -> dict:
    """Atiende un mensaje y registra la interacción. Siempre devuelve un dict con 'interaction_id'."""
    inicio = time.monotonic()
    limite = inicio + config.TIMEOUT_S
    ctx: dict = {}
    try:
        resultado = _procesar(session_id, mensaje, limite, ctx)
        if time.monotonic() > limite:
            resultado = _derivar("timeout")
    except llm.LLMNoDisponible as e:
        log.warning("LLM no disponible: %s", e)
        resultado = _derivar("timeout")
    except Exception:  # noqa: BLE001
        log.exception("Error inesperado procesando la consulta")
        resultado = _derivar("error")

    ctx.setdefault("pregunta", recepcion.recibir(mensaje))
    interaction_id = registro.registrar_interaccion(
        session_id=session_id, pregunta_enmascarada=ctx.get("pregunta"), tema=ctx.get("tema"),
        intencion=ctx.get("intencion"), riesgo=ctx.get("riesgo"), fichas_ids=ctx.get("fichas_ids"),
        score_top1=ctx.get("score_top1"), tool_usada=ctx.get("tool_usada"), derivado=resultado["derivado"],
        motivo_derivacion=resultado["motivo_derivacion"], latencia_ms=int((time.monotonic() - inicio) * 1000),
        tokens_in=ctx.get("tokens_in", 0), tokens_out=ctx.get("tokens_out", 0),
        costo_usd=llm.costo_usd(ctx.get("tokens_in", 0), ctx.get("tokens_out", 0)),
        version_prompts=prompts.version_prompts(),
    )
    return {"interaction_id": interaction_id, **resultado}
