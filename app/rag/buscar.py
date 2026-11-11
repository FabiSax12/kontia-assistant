"""Búsqueda por coseno (numpy) sobre el índice de fichas."""
import json
from functools import lru_cache

import numpy as np

from app import config


@lru_cache(maxsize=1)
def _modelo():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=config.MODELO_EMBEDDINGS)


@lru_cache(maxsize=1)
def _cargar_indice() -> tuple[np.ndarray, list[dict]]:
    if not config.RUTA_INDICE.exists() or not config.RUTA_FICHAS_JSON.exists():
        from app.rag.indexar import indexar

        indexar()
    vectores = np.load(config.RUTA_INDICE)["vectores"]
    fichas = json.loads(config.RUTA_FICHAS_JSON.read_text(encoding="utf-8"))
    return vectores, fichas


def recargar_indice() -> None:
    _cargar_indice.cache_clear()


def buscar(consulta: str, tema: str | None = None, k: int = config.TOP_K) -> list[dict]:
    """Devuelve hasta k fichas ordenadas por similitud, cada una con su 'score'.

    Si 'tema' coincide con alguna ficha, filtra por él; si ninguna ficha tiene ese tema, busca en todas.
    """
    vectores, fichas = _cargar_indice()
    vector = np.array(list(_modelo().embed([consulta])), dtype=np.float32)[0]
    vector /= np.linalg.norm(vector)
    scores = vectores @ vector

    indices = list(range(len(fichas)))
    if tema:
        filtrados = [i for i in indices if fichas[i]["tema"] == tema]
        indices = filtrados or indices
    indices.sort(key=lambda i: scores[i], reverse=True)
    return [{**fichas[i], "score": float(scores[i])} for i in indices[:k]]


def hay_ficha_suficiente(resultados: list[dict]) -> bool:
    return bool(resultados) and resultados[0]["score"] >= config.UMBRAL_SIMILITUD
