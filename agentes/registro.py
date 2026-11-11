"""Agente de registro (sin LLM): guarda cada interacción en SQLite SIN datos personales.

La pregunta que llega aquí ya está enmascarada por recepción.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app import config

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS interacciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    session_id TEXT,
    pregunta_enmascarada TEXT,
    tema TEXT,
    intencion TEXT,
    riesgo TEXT,
    fichas_ids TEXT,
    score_top1 REAL,
    tool_usada TEXT,
    derivado INTEGER NOT NULL DEFAULT 0,
    motivo_derivacion TEXT,
    latencia_ms INTEGER,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    costo_usd REAL DEFAULT 0,
    version_prompts TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    interaction_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS derivaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL,
    contacto TEXT NOT NULL,
    consentimiento_ts TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente'
);
"""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _conexion():
    config.DIR_DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(config.RUTA_DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def iniciar_db() -> None:
    with _conexion() as con:
        con.executescript(_ESQUEMA)


def registrar_interaccion(**d) -> int:
    with _conexion() as con:
        cur = con.execute(
            """INSERT INTO interacciones (ts, session_id, pregunta_enmascarada, tema, intencion, riesgo, fichas_ids,
               score_top1, tool_usada, derivado, motivo_derivacion, latencia_ms, tokens_in, tokens_out, costo_usd,
               version_prompts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_ahora(), d.get("session_id"), d.get("pregunta_enmascarada"), d.get("tema"), d.get("intencion"),
             d.get("riesgo"), d.get("fichas_ids"), d.get("score_top1"), d.get("tool_usada"),
             int(bool(d.get("derivado"))), d.get("motivo_derivacion"), d.get("latencia_ms"),
             d.get("tokens_in", 0), d.get("tokens_out", 0), d.get("costo_usd", 0.0), d.get("version_prompts")),
        )
        return cur.lastrowid


def existe_interaccion(interaction_id: int) -> bool:
    with _conexion() as con:
        return con.execute("SELECT 1 FROM interacciones WHERE id=?", (interaction_id,)).fetchone() is not None


def guardar_feedback(interaction_id: int, rating: int) -> None:
    with _conexion() as con:
        con.execute("INSERT INTO feedback (interaction_id, rating, ts) VALUES (?,?,?)", (interaction_id, rating, _ahora()))


def guardar_derivacion(interaction_id: int, contacto: str) -> int:
    ahora = _ahora()
    with _conexion() as con:
        cur = con.execute(
            "INSERT INTO derivaciones (interaction_id, contacto, consentimiento_ts, estado) VALUES (?,?,?, 'pendiente')",
            (interaction_id, contacto, ahora),
        )
        return cur.lastrowid


def metricas() -> dict:
    with _conexion() as con:
        filas = con.execute("SELECT derivado, latencia_ms, costo_usd FROM interacciones").fetchall()
        rating = con.execute("SELECT AVG(rating) FROM feedback").fetchone()[0]
    total = len(filas)
    latencias = sorted(f["latencia_ms"] for f in filas if f["latencia_ms"] is not None)
    p95 = latencias[min(len(latencias) - 1, int(0.95 * len(latencias)))] if latencias else 0
    return {
        "total_consultas": total,
        "porcentaje_derivadas": round(100 * sum(f["derivado"] for f in filas) / total, 1) if total else 0.0,
        "latencia_promedio_ms": round(sum(latencias) / len(latencias)) if latencias else 0,
        "latencia_p95_ms": p95,
        "rating_promedio": round(rating, 2) if rating is not None else None,
        "costo_estimado_total_usd": round(sum(f["costo_usd"] or 0 for f in filas), 6),
    }
