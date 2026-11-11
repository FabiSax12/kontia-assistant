"""API de Kontia: chat, feedback, derivación, métricas y salud. Sirve static/ en /."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentes import registro
from app import config, llm, orquestador
from app.rag import buscar

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kontia")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    registro.iniciar_db()
    # Precarga el índice y el modelo de embeddings para que la primera consulta no gaste el presupuesto de 10 s.
    await asyncio.to_thread(lambda: (buscar._cargar_indice(), buscar._modelo()))
    log.info("Modo %s", "MOCK (sin GEMINI_API_KEY)" if llm.modo_mock() else "Gemini")
    yield


app = FastAPI(title="Asistente Kontia", lifespan=ciclo_de_vida)


class ChatEntrada(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    mensaje: str = Field(min_length=1, max_length=5000)


class FeedbackEntrada(BaseModel):
    interaction_id: int
    rating: int = Field(ge=1, le=5)


class DerivacionEntrada(BaseModel):
    interaction_id: int
    contacto: str = Field(min_length=3, max_length=200)
    acepto: bool


@app.post("/api/chat")
async def chat(entrada: ChatEntrada):
    try:
        # Margen de 2 s sobre el presupuesto interno; el orquestador ya corta por su cuenta.
        return await asyncio.wait_for(
            asyncio.to_thread(orquestador.atender, entrada.session_id, entrada.mensaje), config.TIMEOUT_S + 2
        )
    except asyncio.TimeoutError:
        return {
            "interaction_id": None,
            "respuesta": f"{orquestador.MENSAJES_DERIVACION['timeout']}\n\n{config.AVISO_FIJO}",
            "ficha": None, "calculo": None, "siguiente_paso": "Pedir revisión de un contador.",
            "derivado": True, "motivo_derivacion": "timeout",
        }


@app.post("/api/feedback")
def feedback(entrada: FeedbackEntrada):
    if not registro.existe_interaccion(entrada.interaction_id):
        raise HTTPException(404, "La interacción no existe")
    registro.guardar_feedback(entrada.interaction_id, entrada.rating)
    return {"ok": True}


@app.post("/api/derivacion")
def derivacion(entrada: DerivacionEntrada):
    if not entrada.acepto:
        raise HTTPException(400, "Necesitamos tu consentimiento para guardar tu contacto")
    if not registro.existe_interaccion(entrada.interaction_id):
        raise HTTPException(404, "La interacción no existe")
    return {"ok": True, "id": registro.guardar_derivacion(entrada.interaction_id, entrada.contacto)}


@app.get("/api/metricas")
def metricas():
    return registro.metricas()


@app.get("/api/health")
def health():
    return {"estado": "ok", "modo": "mock" if llm.modo_mock() else "gemini"}


app.mount("/", StaticFiles(directory=config.DIR_STATIC, html=True), name="static")
