import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..persistence import Snapshots
from ..routing.planner import Planner
from ..simulator.engine import Simulador
from ..world.graph import Grafo
from ..world.mundo import Mundo
from .auth import key_valida, lectura_estado, verificar_api_key

GRAFO = Grafo.desde_archivo(os.environ.get("GRAPH_PATH", "data/manta_graph.json"))
PRO_CAPACIDAD = os.environ.get("PRO_CAPACIDAD", "1") != "0"
PRO_FLOTA = os.environ.get("PRO_FLOTA", "1") != "0"
PLANNER = Planner(GRAFO, prediccion=os.environ.get("PRO_PREDICCION", "1") != "0", capacidad=PRO_CAPACIDAD,
                  flota=PRO_FLOTA)
MUNDO = Mundo(GRAFO, PLANNER)
SNAPSHOTS = Snapshots()


async def _consulta_directa(sid, nodo, turno):
    """SIM_MODO=directo: el simulador llama al planner sin pasar por HTTP (sin overhead de
    cliente en el mismo proceso). SIM_MODO=http (default) usa POST /paso por localhost."""
    MUNDO.asegurar_planner()
    return PLANNER.siguiente_nodo(nodo, sid)


SIM = Simulador(MUNDO, consulta=_consulta_directa if os.environ.get("SIM_MODO", "http") == "directo" else None,
                turno_s=float(os.environ.get("TURNO_S", "2.0")), turnos_ronda=int(os.environ.get("TURNOS_RONDA", "150")),
                snapshots=SNAPSHOTS, reponer=os.environ.get("SIM_POBLACION", "continua") != "fija",
                capacidad=PRO_CAPACIDAD, flota=PRO_FLOTA)


@asynccontextmanager
async def lifespan(app):
    modo = os.environ.get("SIM_AUTOSTART", "none")
    if modo != "none":
        SIM.iniciar(modo)
    yield
    await SIM.detener()


app = FastAPI(title="Escape de Manta Zombie", lifespan=lifespan)


class OrigenSecreto:
    """Opcional (ORIGIN_SECRET): solo acepta trafico con el header x-origin-verify que
    CloudFront agrega al origen ALB. /salud queda libre para el health check del ALB."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        secreto = os.environ.get("ORIGIN_SECRET", "")
        if secreto and scope["type"] in ("http", "websocket") and scope["path"] != "/salud":
            h = {k.decode().lower(): v for k, v in scope["headers"]}
            if not secrets.compare_digest(h.get("x-origin-verify", b""), secreto.encode()):
                if scope["type"] == "http":
                    await send({"type": "http.response.start", "status": 403,
                                "headers": [(b"content-type", b"text/plain")]})
                    await send({"type": "http.response.body", "body": b"forbidden"})
                else:
                    await send({"type": "websocket.close", "code": 1008})
                return
        await self.app(scope, receive, send)


class PasoRapido:
    """Ruta caliente: POST /paso atendido directo en ASGI (sin pydantic ni DI de FastAPI) para
    bajar la CPU por peticion. Mismo contrato y misma autenticacion que la ruta de FastAPI."""

    def __init__(self, app):
        self.app = app

    async def _responder(self, send, status, cuerpo):
        datos = json.dumps(cuerpo).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(datos)).encode())]})
        await send({"type": "http.response.body", "body": datos})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/paso" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        clave = dict(scope["headers"]).get(b"x-api-key", b"").decode("utf-8", "replace")
        if not key_valida(clave):
            return await self._responder(send, 401, {"detail": "API key invalida"})
        cuerpo = b""
        while True:
            msg = await receive()
            cuerpo += msg.get("body", b"")
            if not msg.get("more_body"):
                break
        try:
            d = json.loads(cuerpo)
            nodo, sid, _ = d["nodoActual"], str(d["sobrevivienteId"]), int(d["turno"])
            if not isinstance(nodo, str):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return await self._responder(send, 422, {"detail": "cuerpo invalido"})
        MUNDO.asegurar_planner()
        await self._responder(send, 200, {"siguienteNodo": PLANNER.siguiente_nodo(nodo, sid)})


app.add_middleware(PasoRapido)
app.add_middleware(OrigenSecreto)  # el ultimo agregado es el mas externo: valida origen primero


class PasoIn(BaseModel):
    sobrevivienteId: str
    nodoActual: str
    turno: int


@app.get("/salud")
def salud():
    return {"ok": True}


@app.get("/estado", dependencies=[Depends(lectura_estado)])
async def estado():
    return Response(content=MUNDO.json_estado(), media_type="application/json")


@app.post("/paso", dependencies=[Depends(verificar_api_key)])
async def paso(p: PasoIn):
    # async: el calculo es trivial (lookup en tablas precalculadas), asi se evita el
    # cambio de hilo del threadpool. No recalcula por peticion: usa el planner del turno.
    MUNDO.asegurar_planner()
    return {"siguienteNodo": PLANNER.siguiente_nodo(p.nodoActual, p.sobrevivienteId)}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    publico = os.environ.get("PUBLIC_STATE", "true").lower() != "false"
    if not publico and not key_valida(websocket.headers.get("x-api-key") or websocket.query_params.get("key")):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    ultimo, silencio = None, 0
    try:
        while True:
            est = MUNDO.estado
            if est is not ultimo:
                await websocket.send_text(MUNDO.json_estado())
                ultimo, silencio = est, 0
            elif silencio >= 80:  # ~20 s sin cambios: heartbeat para no caer por inactividad
                await websocket.send_json({"ping": True})
                silencio = 0
            await asyncio.sleep(0.25)
            silencio += 1
    except (WebSocketDisconnect, RuntimeError):
        pass


# Control del simulador. Van bajo /ws/ porque el plan Free de CloudFront permite solo 5
# behaviors y /ws* ya enruta al ALB. Todos exigen API key.
@app.post("/ws/sim/iniciar", dependencies=[Depends(verificar_api_key)])
async def sim_iniciar(ronda: str = "ciclo"):
    try:
        SIM.iniciar(ronda)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"iniciado": ronda}


@app.post("/ws/sim/detener", dependencies=[Depends(verificar_api_key)])
async def sim_detener():
    await SIM.detener()
    return {"detenido": True}


@app.post("/ws/sim/reanudar", dependencies=[Depends(verificar_api_key)])
async def sim_reanudar():
    snap = await asyncio.to_thread(SNAPSHOTS.ultimo)
    if not snap:
        raise HTTPException(404, "no hay snapshot en DynamoDB")
    try:
        SIM.reanudar(snap)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"reanudado": True, "ronda": snap["ronda"], "turno": snap["turno"]}


@app.get("/ws/sim/resultados", dependencies=[Depends(verificar_api_key)])
def sim_resultados():
    return {"corriendo": SIM.corriendo, "resultados": SIM.resultados, "puntaje": SIM.puntaje()}
