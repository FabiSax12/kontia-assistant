"""Modelos Pydantic compartidos entre agentes."""
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Tema(str, Enum):
    aguinaldo = "aguinaldo"
    ccss = "ccss"
    hacienda = "hacienda"
    ins = "ins"
    despido = "despido"
    otro = "otro"


class Parametros(BaseModel):
    salario_mensual: float | None
    fecha_ingreso: str | None
    fecha_salida: str | None
    n_empleados: int | None


class Analisis(BaseModel):
    tema: Tema
    intencion: Literal["info", "calculo", "tramite"]
    riesgo: Literal["bajo", "alto"]
    requiere_calculo: bool
    parametros: Parametros
