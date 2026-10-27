import asyncio
import gc
import json
import os
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect

from ..persistence import Snapshots
from ..routing.planner import Planner
from ..simulator.engine import Simulador, log_json
from ..world.graph import Grafo
from ..world.mundo import Mundo
from .auth import key_valida, lectura_estado, verificar_admin_key

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


async def autoarranque(modo, intentos=300):
    """SIM_AUTOSTART: uvicorn corre el lifespan ANTES de abrir el socket, asi que con SIM_MODO=http
    el turno 1 perdia todas sus consultas. Se espera a que el puerto acepte conexiones (max ~30 s)."""
    u = urlsplit(os.environ.get("SIM_URL", "http://127.0.0.1:8000"))
    for _ in range(intentos):
        try:
            _, w = await asyncio.open_connection(u.hostname, u.port or 80)
            w.close()
            break
        except OSError:
            await asyncio.sleep(0.1)
    SIM.iniciar(modo)


MODOS_AUTOSTART = ("none", "1", "2", "3", "ciclo", "demo")


@asynccontextmanager
async def lifespan(app):
    modo = os.environ.get("SIM_AUTOSTART", "none")
    if modo not in MODOS_AUTOSTART:  # antes el ValueError se perdia dentro de la tarea, sin rastro
        log_json("config_invalida", variable="SIM_AUTOSTART", valor=modo, validos=list(MODOS_AUTOSTART))
        modo = "none"  # /paso sigue sirviendo; la ronda se inicia desde el panel del operador
    if os.environ.get("API_KEY") and not os.environ.get("ADMIN_API_KEY"):
        log_json("aviso", texto="ADMIN_API_KEY no definida: /ws/sim/* acepta la API_KEY de /paso "
                                "(solo para desarrollo local)")
    try:
        await asyncio.to_thread(SNAPSHOTS.preparar)
    except Exception as e:  # sin credenciales (local) o sin red: el juego sigue sin snapshots
        log_json("aviso", texto=f"DynamoDB no disponible al arrancar: {e!r}")
    # el grafo, el planner y boto3 ya estan cargados: se congelan para que las colecciones
    # completas del GC (16-37 ms) no los recorran durante las rafagas de /paso
    gc.collect()
    gc.freeze()
    tarea = asyncio.create_task(autoarranque(modo)) if modo != "none" else None
    yield
    if tarea:
        tarea.cancel()
    await SIM.detener()


# /docs y /openapi.json listan los endpoints de control: apagados salvo EXPONER_DOCS=1 (desarrollo)
_DOCS = os.environ.get("EXPONER_DOCS", "0") == "1"
app = FastAPI(title="Escape de Manta Zombie", lifespan=lifespan, docs_url="/docs" if _DOCS else None,
              redoc_url=None, openapi_url="/openapi.json" if _DOCS else None)


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


MAX_CUERPO = 4096  # bytes: una consulta valida pesa ~80


def _entero(x):
    """turno: entero (acepta 142, 142.0 o "142"); rechaza bool, infinitos y decimales."""
    if isinstance(x, bool):
        raise ValueError
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, str) and x.strip().lstrip("-").isdigit():
        return int(x)
    raise ValueError


def leer_paso(cuerpo):
    """(nodo, sobreviviente) de un cuerpo de POST /paso; ValueError si no cumple el contrato."""
    d = json.loads(cuerpo)
    nodo, sid = d["nodoActual"], d["sobrevivienteId"]
    _entero(d["turno"])
    if isinstance(sid, int) and not isinstance(sid, bool):
        sid = str(sid)
    if not (isinstance(nodo, str) and isinstance(sid, str) and len(nodo) <= 64 and len(sid) <= 64):
        raise ValueError
    return nodo, sid


class PasoRapido:
    """Ruta caliente: POST /paso atendido directo en ASGI (sin pydantic ni DI de FastAPI) para
    bajar la CPU por peticion. No recalcula nada: lee las tablas del planner del turno."""

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
            if len(cuerpo) > MAX_CUERPO:
                return await self._responder(send, 413, {"detail": "cuerpo demasiado grande"})
            if not msg.get("more_body"):
                break
        try:
            nodo, sid = leer_paso(cuerpo)
        except Exception:  # JSON invalido, campos faltantes o de otro tipo, turno infinito...
            return await self._responder(send, 422, {"detail": "cuerpo invalido"})
        MUNDO.asegurar_planner()
        await self._responder(send, 200, {"siguienteNodo": PLANNER.siguiente_nodo(nodo, sid)})


app.add_middleware(PasoRapido)
app.add_middleware(OrigenSecreto)  # el ultimo agregado es el mas externo: valida origen primero



@app.get("/salud")
def salud():
    return {"ok": True}


@app.get("/estado", dependencies=[Depends(lectura_estado)])
async def estado():
    return Response(content=MUNDO.json_estado(), media_type="application/json")


MAX_WS = int(os.environ.get("MAX_WS", "100"))  # visores simultaneos; el resto cae a polling
_visores = 0


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    global _visores
    publico = os.environ.get("PUBLIC_STATE", "true").lower() != "false"
    if not publico and not key_valida(websocket.headers.get("x-api-key") or websocket.query_params.get("key")):
        await websocket.close(code=4401)
        return
    if _visores >= MAX_WS:
        await websocket.close(code=1013)  # "intenta mas tarde": el mapa sigue por polling a /estado
        return
    await websocket.accept()
    _visores += 1
    lector = asyncio.create_task(_escuchar(websocket))
    ultimo, silencio = None, 0
    try:
        while not lector.done():
            est = MUNDO.estado
            if est is not ultimo:
                await websocket.send_text(MUNDO.json_estado())
                ultimo, silencio = est, 0
            elif silencio >= 80:  # ~20 s sin cambios: heartbeat para no caer por inactividad
                await websocket.send_json({"ping": True})
                silencio = 0
            await asyncio.sleep(0.25)
            silencio += 1
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        lector.cancel()
        _visores -= 1


async def _escuchar(websocket):
    """El mapa solo escucha. Sin leer, uvicorn acumulaba en memoria lo que mandara el cliente (2
    conexiones anonimas llevaban la tarea a ~1 GB) y un visor caido ocupaba su cupo hasta el
    siguiente envio. Cualquier mensaje de datos cierra con 1008; una desconexion termina al instante."""
    try:
        if (await websocket.receive())["type"] != "websocket.disconnect":
            await websocket.close(code=1008)
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass


# Control del simulador. Van bajo /ws/ porque el plan Free de CloudFront permite solo 5
# behaviors y /ws* ya enruta al ALB. Exigen la key de operador (ADMIN_API_KEY), no la de /paso.
@app.post("/ws/sim/iniciar", dependencies=[Depends(verificar_admin_key)])
async def sim_iniciar(ronda: str = "ciclo"):
    try:
        SIM.iniciar(ronda)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"iniciado": ronda}


@app.post("/ws/sim/detener", dependencies=[Depends(verificar_admin_key)])
async def sim_detener():
    await SIM.detener()
    return {"detenido": True}


@app.post("/ws/sim/reanudar", dependencies=[Depends(verificar_admin_key)])
async def sim_reanudar():
    snap = await asyncio.to_thread(SNAPSHOTS.ultimo)
    if not snap:
        raise HTTPException(404, "no hay snapshot en DynamoDB")
    try:
        SIM.reanudar(snap)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"reanudado": True, "ronda": snap["ronda"], "turno": snap["turno"]}


@app.get("/ws/sim/resultados", dependencies=[Depends(verificar_admin_key)])
def sim_resultados():
    return {"corriendo": SIM.corriendo, "resultados": SIM.resultados, "puntaje": SIM.puntaje()}


# Desarrollo local o plan B sin AWS: SERVIR_FRONTEND=1 sirve el mapa y el grafo desde este mismo
# proceso. En AWS no se activa: los sirve S3 a traves de CloudFront.
if os.environ.get("SERVIR_FRONTEND", "0") == "1":
    from fastapi.responses import FileResponse

    @app.get("/", include_in_schema=False)
    def mapa_local():
        return FileResponse(os.path.join(os.environ.get("FRONTEND_DIR", "frontend"), "index.html"))

    @app.get("/manta_graph.json", include_in_schema=False)
    def grafo_local():
        return FileResponse(os.environ.get("GRAPH_PATH", "data/manta_graph.json"), media_type="application/json")
