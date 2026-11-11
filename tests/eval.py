"""Corre tests/escenarios.yaml contra /api/chat y reporta métricas. Guarda un CSV para que el contador lo califique.

Uso (con el servidor corriendo, `make dev`):  python tests/eval.py [URL_BASE]
Variables: PAUSA_EVAL_S (pausa entre escenarios, default 4; cuida la cuota del tier gratuito).
"""
import csv
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
URL = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
PAUSA = float(os.getenv("PAUSA_EVAL_S", "4"))
RUTA_DB = RAIZ / "data" / "kontia.db"


def post(ruta: str, cuerpo: dict) -> dict:
    req = urllib.request.Request(
        URL + ruta, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def datos_db(interaction_id: int) -> dict:
    con = sqlite3.connect(RUTA_DB)
    con.row_factory = sqlite3.Row
    fila = con.execute("SELECT tema, costo_usd FROM interacciones WHERE id=?", (interaction_id,)).fetchone()
    con.close()
    return dict(fila) if fila else {"tema": None, "costo_usd": 0}


def montos_en(texto: str) -> set[int]:
    return {int(re.sub(r"\D", "", m)) for m in re.findall(r"₡\s?(\d[\d  .,]*\d|\d)", texto)}


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f} %" if b else "n/a"


def main() -> None:
    escenarios = yaml.safe_load((RAIZ / "tests" / "escenarios.yaml").read_text(encoding="utf-8"))
    filas, latencias = [], []
    ok_tema = ok_deriva = montos_total = montos_ok = costo = 0

    for i, e in enumerate(escenarios):
        if i:
            time.sleep(PAUSA)
        t0 = time.monotonic()
        r = post("/api/chat", {"session_id": "eval", "mensaje": e["pregunta"]})
        latencias.append((time.monotonic() - t0) * 1000)
        db = datos_db(r["interaction_id"]) if r.get("interaction_id") else {"tema": None, "costo_usd": 0}
        costo += db["costo_usd"] or 0

        tema_ok = db["tema"] == e["tema_esperado"]
        deriva_ok = r["derivado"] == e["debe_derivar"]
        ficha_id = (r["ficha"] or {}).get("id")
        ok_tema += tema_ok
        ok_deriva += deriva_ok
        monto_ok = ""
        if e.get("monto_esperado") is not None:
            montos_total += 1
            monto_ok = e["monto_esperado"] in montos_en(r["respuesta"])
            montos_ok += monto_ok
        filas.append({
            "pregunta": e["pregunta"], "tema_esperado": e["tema_esperado"], "tema_obtenido": db["tema"],
            "tema_ok": tema_ok, "debe_derivar": e["debe_derivar"], "derivado": r["derivado"], "derivacion_ok": deriva_ok,
            "ficha_esperada": e.get("ficha_esperada"), "ficha_obtenida": ficha_id,
            "monto_esperado": e.get("monto_esperado"), "monto_ok": monto_ok,
            "respuesta": r["respuesta"], "respuesta_contador": e.get("respuesta_contador"),
            "correcta_segun_contador (si/no)": "",
        })
        print(f"[{i + 1}/{len(escenarios)}] tema={'OK' if tema_ok else 'X'} deriva={'OK' if deriva_ok else 'X'} {e['pregunta'][:60]}")

    latencias.sort()
    p95 = latencias[min(len(latencias) - 1, int(0.95 * len(latencias)))] if latencias else 0
    n = len(escenarios)
    print("\n=== Resultados ===")
    print(f"Clasificación correcta : {pct(ok_tema, n)} ({ok_tema}/{n})")
    print(f"Derivación correcta    : {pct(ok_deriva, n)} ({ok_deriva}/{n})")
    print(f"Montos exactos         : {pct(montos_ok, montos_total)} ({montos_ok}/{montos_total})")
    print(f"Latencia p95           : {p95:.0f} ms")
    print(f"Costo total estimado   : ${costo:.6f} USD")

    salida = RAIZ / "tests" / f"resultados_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with salida.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"CSV para el contador: {salida}")


if __name__ == "__main__":
    main()
