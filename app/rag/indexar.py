"""Indexa fichas/*.md: parsea frontmatter, genera embeddings y guarda data/indice.npz + data/fichas.json.

Uso: python -m app.rag.indexar
"""
import json
import re

import numpy as np
import yaml

from app import config

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def leer_fichas() -> list[dict]:
    fichas = []
    for ruta in sorted(config.DIR_FICHAS.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        m = _FRONTMATTER.match(ruta.read_text(encoding="utf-8"))
        if not m:
            raise ValueError(f"{ruta.name}: falta el frontmatter YAML")
        meta = yaml.safe_load(m.group(1))
        faltan = {"id", "titulo", "tema", "sensible", "fuente_oficial", "fecha_revision", "revisado_por"} - set(meta)
        if faltan:
            raise ValueError(f"{ruta.name}: faltan campos {sorted(faltan)}")
        meta["fecha_revision"] = str(meta["fecha_revision"])
        meta["cuerpo"] = m.group(2).strip()
        fichas.append(meta)
    return fichas


def generar_embeddings(textos: list[str]) -> np.ndarray:
    from fastembed import TextEmbedding

    modelo = TextEmbedding(model_name=config.MODELO_EMBEDDINGS)
    vectores = np.array(list(modelo.embed(textos)), dtype=np.float32)
    return vectores / np.linalg.norm(vectores, axis=1, keepdims=True)


def indexar() -> int:
    fichas = leer_fichas()
    if not fichas:
        raise SystemExit("No hay fichas en fichas/")
    textos = [f"{f['titulo']}. {f['cuerpo']}" for f in fichas]
    vectores = generar_embeddings(textos)
    config.DIR_DATA.mkdir(exist_ok=True)
    np.savez(config.RUTA_INDICE, vectores=vectores)
    config.RUTA_FICHAS_JSON.write_text(json.dumps(fichas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Indexadas {len(fichas)} fichas -> {config.RUTA_INDICE.name}, {config.RUTA_FICHAS_JSON.name}")
    return len(fichas)


if __name__ == "__main__":
    indexar()
