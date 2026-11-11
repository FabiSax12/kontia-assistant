"""Carga prompts/*.md. La primera línea 'VERSION: x' se guarda en cada registro."""
from app import config


def cargar(nombre: str) -> tuple[str, str]:
    """Devuelve (texto_del_prompt, version)."""
    lineas = (config.DIR_PROMPTS / f"{nombre}.md").read_text(encoding="utf-8").splitlines()
    version = lineas[0].removeprefix("VERSION:").strip()
    return "\n".join(lineas[1:]).strip(), version


def version_prompts() -> str:
    return f"analisis={cargar('analisis')[1]};respuesta={cargar('respuesta')[1]}"
