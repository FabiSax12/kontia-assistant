"""Agente de respuesta (LLM 2): redacta con las top-3 fichas y calcula montos solo con tools.

Loop de function calling manual (automatic function calling desactivado) para registrar la tool usada
y validar que cada monto en colones del texto salga de un resultado de tool.
"""
import json
import re
from dataclasses import dataclass, field

from google.genai import types

from agentes.esquemas import Analisis, Tema
from app import config, llm, prompts
from app.tools.calculadoras import ESQUEMAS, ejecutar_tool

MAX_RONDAS_TOOLS = 4
MAX_PALABRAS_TOLERADAS = 150  # el prompt pide 120; se tolera un margen antes de reintentar


class RespuestaInvalida(Exception):
    """La salida del modelo no pasó la validación (ficha inexistente o monto que no viene de una tool)."""


@dataclass
class Resultado:
    sin_ficha: bool = False
    respuesta: str = ""
    siguiente_paso: str = ""
    ficha: dict | None = None
    calculo: dict | None = None
    tool_usada: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    resultados_tools: list = field(default_factory=list)


# ---------- utilidades ----------

def formato_colones(n: int) -> str:
    return "₡" + f"{n:,}".replace(",", " ")


def _seccion(ficha: dict, titulo: str) -> str:
    m = re.search(rf"##\s*{re.escape(titulo)}[^\n]*\n(.*?)(?=\n##|\Z)", ficha["cuerpo"], re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _recortar(texto: str, palabras: int) -> str:
    p = texto.split()
    return texto if len(p) <= palabras else " ".join(p[:palabras]) + "…"


_RE_MONTO = re.compile(r"₡\s?(\d[\d  .,]*)|(\d[\d  .,]*)\s?colones", re.IGNORECASE)


def montos_en_texto(texto: str) -> list[int]:
    montos = []
    for m in _RE_MONTO.finditer(texto):
        crudo = (m.group(1) or m.group(2)).strip(" .,")
        crudo = re.sub(r"[.,]\d{2}$", "", crudo)  # quita decimales tipo ",00"
        digitos = re.sub(r"\D", "", crudo)
        if digitos:
            montos.append(int(digitos))
    return montos


def _enteros(obj) -> set[int]:
    if isinstance(obj, bool):
        return set()
    if isinstance(obj, (int, float)):
        return {int(round(obj))}
    if isinstance(obj, dict):
        return set().union(*(_enteros(v) for v in obj.values())) if obj else set()
    if isinstance(obj, (list, tuple)):
        return set().union(*(_enteros(v) for v in obj)) if obj else set()
    return set()


def montos_validos(texto: str, resultados_tools: list[dict]) -> bool:
    permitidos = _enteros(resultados_tools)
    return all(m in permitidos for m in montos_en_texto(texto))


def armar_mensaje(respuesta: str, siguiente_paso: str, ficha: dict) -> str:
    return (
        f"{respuesta}\n\n"
        f"Siguiente paso: {siguiente_paso}\n"
        f"Fuente: {ficha['titulo']} (revisada el {ficha['fecha_revision']}). {ficha['fuente_oficial']}\n\n"
        f"{config.AVISO_FIJO}"
    )


def ficha_publica(f: dict) -> dict:
    return {"id": f["id"], "titulo": f["titulo"], "fecha_revision": f["fecha_revision"], "fuente": f["fuente_oficial"]}


# ---------- modo mock ----------

def _mock(fichas: list[dict], analisis: Analisis) -> Resultado:
    ficha = fichas[0]
    p = analisis.parametros
    r = Resultado(ficha=ficha)
    texto = ""
    if analisis.tema == Tema.aguinaldo and p.salario_mensual:
        args = {k: v for k, v in {"salario_mensual": p.salario_mensual, "fecha_ingreso": p.fecha_ingreso,
                                  "fecha_salida": p.fecha_salida}.items() if v}
        res = ejecutar_tool("calcular_aguinaldo", args)
        r.tool_usada, r.calculo = "calcular_aguinaldo", res
        lim = res["fecha_limite"]
        meses = f"{res['meses_contados']} meses" + (f" y {res['dias_residuales']} días" if res["dias_residuales"] else "")
        texto = (f"Con un salario de {formato_colones(res['salario_mensual'])}, el aguinaldo es de "
                 f"{formato_colones(res['monto'])} ({meses} contados del periodo). "
                 f"Fecha límite de pago: {int(lim[8:])} de diciembre de {lim[:4]}. No paga cargas sociales.")
    elif analisis.tema == Tema.ccss and p.salario_mensual:
        args = {"salario_bruto": p.salario_mensual}
        if p.n_empleados:
            args["n_empleados"] = p.n_empleados
        res = ejecutar_tool("calcular_cargas_sociales", args)
        r.tool_usada, r.calculo = "calcular_cargas_sociales", res
        texto = (f"Sobre un salario bruto de {formato_colones(res['salario_bruto'])}: la cuota patronal es de "
                 f"{formato_colones(res['patronal'])}, la obrera de {formato_colones(res['obrera'])} y el salario neto "
                 f"antes de renta queda en {formato_colones(res['neto_antes_renta'])}.")
    else:
        texto = _recortar(_seccion(ficha, "Cómo se calcula / cuánto") or _seccion(ficha, "Qué es"), 70)
        if analisis.requiere_calculo:
            texto += " Para calcular un monto exacto, indicame el salario mensual y, si aplica, la fecha de ingreso."
        limite = _seccion(ficha, "Fecha límite")
        if limite and "TODO" not in limite:
            texto += f" Fecha límite: {_recortar(limite, 20)}"
    r.respuesta = texto
    r.siguiente_paso = _recortar(_seccion(ficha, "Siguiente paso"), 40) or "Consultá con un contador."
    return r


# ---------- modo real ----------

def _contenido_inicial(pregunta: str, fichas: list[dict], analisis: Analisis) -> str:
    bloques = "\n\n".join(
        f"<ficha id=\"{f['id']}\" titulo=\"{f['titulo']}\" revision=\"{f['fecha_revision']}\">\n{f['cuerpo']}\n</ficha>"
        for f in fichas
    )
    params = json.dumps(analisis.parametros.model_dump(), ensure_ascii=False)
    return f"<fichas>\n{bloques}\n</fichas>\n\nParámetros detectados: {params}\n\n<pregunta>{pregunta}</pregunta>"


def _ronda_con_tools(modelo: str, contenidos: list, cfg, limite: float, r: Resultado) -> str:
    """Itera function calling a mano hasta obtener texto final."""
    for _ in range(MAX_RONDAS_TOOLS):
        resp = llm.generar(modelo, contenidos, cfg, limite)
        t_in, t_out = llm.tokens(resp)
        r.tokens_in += t_in
        r.tokens_out += t_out
        llamadas = resp.function_calls or []
        if not llamadas:
            return (resp.text or "").strip()
        contenidos.append(resp.candidates[0].content)
        partes = []
        for fc in llamadas:
            try:
                res = ejecutar_tool(fc.name, dict(fc.args or {}))
                r.resultados_tools.append(res)
                if r.tool_usada is None:
                    r.tool_usada, r.calculo = fc.name, res
                salida = res
            except ValueError as e:
                salida = {"error": str(e)}
            partes.append(types.Part.from_function_response(name=fc.name, response={"resultado": salida}))
        contenidos.append(types.Content(role="user", parts=partes))
    raise RespuestaInvalida("Demasiadas rondas de tools")


def _parsear(texto: str, fichas: list[dict]) -> tuple[str, str, dict]:
    m = re.search(r"RESPUESTA:\s*(.*?)\s*SIGUIENTE_PASO:\s*(.*?)\s*FICHA:\s*([\w\-]+)", texto, re.DOTALL)
    if not m:
        raise RespuestaInvalida("Formato de salida inesperado")
    respuesta, paso, ficha_id = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    ficha = next((f for f in fichas if f["id"] == ficha_id), None)
    if ficha is None:
        raise RespuestaInvalida(f"La ficha citada no existe: {ficha_id}")
    return respuesta, paso, ficha


def responder(pregunta: str, fichas: list[dict], analisis: Analisis, limite: float) -> Resultado:
    if llm.modo_mock():
        return _mock(fichas, analisis)

    system, _ = prompts.cargar("respuesta")
    cfg = llm.config_base(system, config.MAX_TOKENS_RESPUESTA)
    cfg.tools = llm.declaraciones_tools(ESQUEMAS)
    cfg.automatic_function_calling = types.AutomaticFunctionCallingConfig(disable=True)
    modelo = llm.modelos()[1]

    r = Resultado()
    contenidos = [types.Content(role="user", parts=[types.Part(text=_contenido_inicial(pregunta, fichas, analisis))])]
    ultimo_error = "desconocido"
    for _ in range(2):  # un intento + un reintento si la validación falla
        texto = _ronda_con_tools(modelo, contenidos, cfg, limite, r)
        if texto.strip().startswith("SIN_FICHA"):
            r.sin_ficha = True
            return r
        try:
            respuesta, paso, ficha = _parsear(texto, fichas)
            if not montos_validos(f"{respuesta} {paso}", r.resultados_tools):
                raise RespuestaInvalida("Hay montos en colones que no vienen de una tool")
            if len(f"{respuesta} {paso}".split()) > MAX_PALABRAS_TOLERADAS:
                raise RespuestaInvalida("La respuesta supera las 120 palabras")
        except RespuestaInvalida as e:
            ultimo_error = str(e)
            contenidos.append(types.Content(role="model", parts=[types.Part(text=texto or "(vacío)")]))
            contenidos.append(types.Content(role="user", parts=[types.Part(text=(
                f"Tu respuesta no es válida: {e}. Corregila: usá el formato exacto, máximo 120 palabras, una ficha "
                "de las recibidas y montos solo si vienen de una tool."))]))
            continue
        r.respuesta, r.siguiente_paso = respuesta, paso
        r.ficha = ficha
        return r
    raise RespuestaInvalida(ultimo_error)
