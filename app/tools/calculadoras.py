"""Calculadoras de cumplimiento. Los montos SIEMPRE salen de aquí, nunca del LLM.

Redondeo a colones enteros (mitad hacia arriba). Cada función tiene su esquema JSON
(ver ESQUEMAS) para exponerla como tool de function calling.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app import config


def _redondear(valor: Decimal) -> int:
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _dec(x: Any) -> Decimal:
    return Decimal(str(x))


def _a_fecha(valor: date | str | None) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def _sumar_meses(f: date, meses: int) -> date:
    indice = f.month - 1 + meses
    anio, mes = f.year + indice // 12, indice % 12 + 1
    dia = min(f.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def calcular_aguinaldo(
    salario_mensual: float,
    fecha_ingreso: date | str | None = None,
    fecha_salida: date | str | None = None,
    anio: int = 2026,
) -> dict:
    """Aguinaldo = salario mensual x (meses + días/30) / 12, sobre el periodo 1-dic a 30-nov.

    Meses completos + días residuales (cada día = salario/30, luego dividido entre 12).
    """
    inicio_periodo = date(anio - 1, 12, 1)
    fin_periodo = date(anio, 11, 30)
    ingreso, salida = _a_fecha(fecha_ingreso), _a_fecha(fecha_salida)

    inicio = max(ingreso, inicio_periodo) if ingreso else inicio_periodo
    fin = min(salida, fin_periodo) if salida else fin_periodo

    meses, dias = 0, 0
    if fin >= inicio:
        # meses completos: el mes n termina el día anterior a inicio + n meses
        while _sumar_meses(inicio, meses + 1) - timedelta(days=1) <= fin and meses < 12:
            meses += 1
        dias = min((fin - _sumar_meses(inicio, meses)).days + 1, 30) if meses < 12 else 0
        dias = max(dias, 0)

    salario = _dec(salario_mensual)
    monto = _redondear(salario * (Decimal(meses) + Decimal(dias) / 30) / 12)
    return {
        "monto": monto,
        "meses_contados": meses,
        "dias_residuales": dias,
        "periodo_inicio": inicio_periodo.isoformat(),
        "periodo_fin": fin_periodo.isoformat(),
        "fecha_limite": date(anio, config.AGUINALDO_MES_LIMITE, config.AGUINALDO_DIA_LIMITE).isoformat(),
        "paga_cargas_sociales": False,
    }


def calcular_cargas_sociales(salario_bruto: float, n_empleados: int = 5) -> dict:
    """CCSS patronal (26.83 %, o 25.33 % con menos de 5 trabajadores), obrera (10.83 %) y neto antes de renta."""
    tasa_patronal = (
        config.TASA_CCSS_PATRONAL_SIN_INA
        if n_empleados < config.UMBRAL_EMPLEADOS_INA
        else config.TASA_CCSS_PATRONAL
    )
    salario = _dec(salario_bruto)
    patronal = _redondear(salario * _dec(tasa_patronal))
    obrera = _redondear(salario * _dec(config.TASA_CCSS_OBRERA))
    return {
        "salario_bruto": _redondear(salario),
        "tasa_patronal": tasa_patronal,
        "tasa_obrera": config.TASA_CCSS_OBRERA,
        "patronal": patronal,
        "obrera": obrera,
        "neto_antes_renta": _redondear(salario) - obrera,
    }


def calcular_costo_empleado(
    salario_mensual: float, meses: int = 12, tasa_ins: float = config.TASA_INS_DEFECTO
) -> dict:
    """Costo del empleado = salario del periodo + aguinaldo + CCSS patronal + INS (sobre el salario)."""
    salario = _dec(salario_mensual)
    salario_total = salario * meses
    aguinaldo = salario_total / 12
    ccss = salario_total * _dec(config.TASA_CCSS_PATRONAL)
    ins = salario_total * _dec(tasa_ins)
    return {
        "salario_periodo": _redondear(salario_total),
        "aguinaldo": _redondear(aguinaldo),
        "ccss_patronal": _redondear(ccss),
        "ins": _redondear(ins),
        "costo_total": _redondear(salario_total) + _redondear(aguinaldo) + _redondear(ccss) + _redondear(ins),
        "meses": meses,
    }


# --- Esquemas JSON (formato neutro, el cliente LLM los convierte a declaraciones de Gemini) ---
ESQUEMAS: list[dict] = [
    {
        "name": "calcular_aguinaldo",
        "description": "Calcula el aguinaldo (monto, meses contados y fecha límite de pago) de un trabajador.",
        "parameters": {
            "type": "object",
            "properties": {
                "salario_mensual": {"type": "number", "description": "Salario mensual bruto en colones"},
                "fecha_ingreso": {"type": "string", "description": "Fecha de ingreso YYYY-MM-DD (opcional)"},
                "fecha_salida": {"type": "string", "description": "Fecha de salida YYYY-MM-DD (opcional)"},
                "anio": {"type": "integer", "description": "Año del aguinaldo (por defecto 2026)"},
            },
            "required": ["salario_mensual"],
        },
    },
    {
        "name": "calcular_cargas_sociales",
        "description": "Calcula CCSS patronal, obrera y salario neto antes de renta.",
        "parameters": {
            "type": "object",
            "properties": {
                "salario_bruto": {"type": "number", "description": "Salario bruto mensual en colones"},
                "n_empleados": {"type": "integer", "description": "Cantidad de trabajadores del patrono (por defecto 5)"},
            },
            "required": ["salario_bruto"],
        },
    },
    {
        "name": "calcular_costo_empleado",
        "description": "Calcula el costo total anual de un empleado para el patrono (salario + aguinaldo + CCSS + INS).",
        "parameters": {
            "type": "object",
            "properties": {
                "salario_mensual": {"type": "number", "description": "Salario mensual bruto en colones"},
                "meses": {"type": "integer", "description": "Meses a calcular (por defecto 12)"},
                "tasa_ins": {"type": "number", "description": "Tasa INS como decimal, ej. 0.02"},
            },
            "required": ["salario_mensual"],
        },
    },
]

FUNCIONES = {
    "calcular_aguinaldo": calcular_aguinaldo,
    "calcular_cargas_sociales": calcular_cargas_sociales,
    "calcular_costo_empleado": calcular_costo_empleado,
}


def ejecutar_tool(nombre: str, argumentos: dict) -> dict:
    """Ejecuta una calculadora por nombre. Lanza ValueError si la tool o los argumentos no sirven."""
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        raise ValueError(f"Tool desconocida: {nombre}")
    try:
        return funcion(**{k: v for k, v in argumentos.items() if v is not None})
    except TypeError as e:
        raise ValueError(f"Argumentos inválidos para {nombre}: {e}") from e
