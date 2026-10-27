import os
import secrets

from fastapi import Header, HTTPException


def key_valida(candidata) -> bool:
    esperada = os.environ.get("API_KEY", "")
    return bool(esperada) and secrets.compare_digest((candidata or "").encode(), esperada.encode())


def verificar_api_key(x_api_key: str = Header(default="")):
    if not key_valida(x_api_key):
        raise HTTPException(status_code=401, detail="API key invalida")


def lectura_estado(x_api_key: str = Header(default="")):
    """/estado es publico por defecto (el navegador no puede guardar una key). Con
    PUBLIC_STATE=false exige la key."""
    if os.environ.get("PUBLIC_STATE", "true").lower() != "false":
        return
    verificar_api_key(x_api_key)
