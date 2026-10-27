import os
import secrets

from fastapi import Header, HTTPException


def key_valida(candidata, variable="API_KEY") -> bool:
    esperada = os.environ.get(variable, "")
    return bool(esperada) and secrets.compare_digest((candidata or "").encode(), esperada.encode())


def verificar_api_key(x_api_key: str = Header(default="")):
    if not key_valida(x_api_key):
        raise HTTPException(status_code=401, detail="API key invalida")


def verificar_admin_key(x_api_key: str = Header(default="")):
    """Control del simulador (/ws/sim/*). Con ADMIN_API_KEY definida exige esa key: la que se
    entrega al jurado para /paso no puede detener ni reiniciar una ronda (minimo privilegio).
    Sin ADMIN_API_KEY (desarrollo local) acepta la API_KEY."""
    variable = "ADMIN_API_KEY" if os.environ.get("ADMIN_API_KEY") else "API_KEY"
    if not key_valida(x_api_key, variable):
        raise HTTPException(status_code=401, detail="API key de operador invalida")


def lectura_estado(x_api_key: str = Header(default="")):
    """/estado es publico por defecto (el navegador no puede guardar una key). Con
    PUBLIC_STATE=false exige la key."""
    if os.environ.get("PUBLIC_STATE", "true").lower() != "false":
        return
    verificar_api_key(x_api_key)
