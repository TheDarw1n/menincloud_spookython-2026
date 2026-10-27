import os
import threading

os.environ["API_KEY"] = "test-key"
from fastapi.testclient import TestClient

from src.api.main import app, MUNDO, PLANNER

c = TestClient(app)
H = {"x-api-key": "test-key"}
P = {"sobrevivienteId": "S", "nodoActual": "N-0001", "turno": 1}


def test_salud():
    assert c.get("/salud").json() == {"ok": True}


def test_paso_sin_key():
    assert c.post("/paso", json=P).status_code == 401
    assert c.post("/paso", headers={"x-api-key": "mala"}, json=P).status_code == 401


def test_paso_ok_y_nodo_desconocido():
    assert c.post("/paso", headers=H, json=P).json()["siguienteNodo"] in ("N-0002", "N-0006")
    r = c.post("/paso", headers=H, json={**P, "nodoActual": "X"})
    assert r.json()["siguienteNodo"] == "X"


def test_estado_publico_y_privado(monkeypatch):
    assert c.get("/estado").status_code == 200
    monkeypatch.setenv("PUBLIC_STATE", "false")
    assert c.get("/estado").status_code == 401
    assert c.get("/estado", headers=H).status_code == 200


def test_websocket_publica_estado():
    with c.websocket_connect("/ws") as ws:
        assert "turno" in ws.receive_json()


def test_origen_secreto(monkeypatch):
    monkeypatch.setenv("ORIGIN_SECRET", "abc")
    assert c.get("/salud").status_code == 200
    assert c.get("/estado").status_code == 403
    assert c.get("/estado", headers={"x-origin-verify": "abc"}).status_code == 200


def test_control_simulador_requiere_key():
    assert c.post("/ws/sim/iniciar").status_code == 401
    assert c.get("/ws/sim/resultados", headers=H).status_code == 200


def test_planner_se_recalcula_una_sola_vez_bajo_concurrencia(monkeypatch):
    llamadas = []
    original = PLANNER.actualizar
    monkeypatch.setattr(PLANNER, "actualizar", lambda *a: (llamadas.append(1), original(*a)))
    MUNDO.estado = dict(MUNDO.estado, turno=777)  # turno nuevo sin publicar aun
    hilos = [threading.Thread(target=MUNDO.asegurar_planner) for _ in range(50)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert len(llamadas) == 1


def test_paso_cuerpo_invalido():
    assert c.post("/paso", headers=H, json={"nodoActual": "N-0001"}).status_code == 422
    assert c.post("/paso", headers=H, content=b"no-json").status_code == 422


def test_estado_se_serializa_una_vez_por_publicacion():
    MUNDO.publicar(metricas={"salvados": 7})
    primero = MUNDO.json_estado()
    assert MUNDO.json_estado() is primero                    # mismo turno: no se vuelve a serializar
    assert c.get("/estado").json()["metricas"] == {"salvados": 7}
    MUNDO.publicar(metricas={"salvados": 8})
    assert MUNDO.json_estado() is not primero and '"salvados":8' in MUNDO.json_estado()


def test_control_del_simulador_exige_la_key_de_operador(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "operador")
    assert c.get("/ws/sim/resultados", headers=H).status_code == 401          # la key de /paso no sirve
    assert c.post("/ws/sim/detener", headers=H).status_code == 401
    assert c.get("/ws/sim/resultados", headers={"x-api-key": "operador"}).status_code == 200
    assert c.post("/paso", headers={"x-api-key": "operador"}, json=P).status_code == 401  # y viceversa
    monkeypatch.delenv("ADMIN_API_KEY")
    assert c.get("/ws/sim/resultados", headers=H).status_code == 200          # local: la misma API_KEY


def test_paso_valida_tipos_y_tamano():
    malos = [{**P, "turno": 1e400}, {**P, "turno": True}, {**P, "turno": 1.5}, {**P, "sobrevivienteId": {"x": [1]}},
             {**P, "nodoActual": 7}, {**P, "nodoActual": "N" * 100}]
    for cuerpo in malos:
        assert c.post("/paso", headers=H, json=cuerpo).status_code == 422, cuerpo
    assert c.post("/paso", headers=H, content=b'{"turno": Infinity, "nodoActual": "N-0001", "sobrevivienteId": "S"}').status_code == 422
    assert c.post("/paso", headers=H, content=b"x" * 5000).status_code == 413
    assert c.post("/paso", headers=H, json={**P, "turno": "142", "sobrevivienteId": 89}).status_code == 200


def test_docs_apagados_por_defecto():
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404


def test_websocket_limita_visores(monkeypatch):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    import src.api.main as api
    monkeypatch.setattr(api, "MAX_WS", 1)
    with c.websocket_connect("/ws") as uno:
        assert "turno" in uno.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/ws") as dos:
                dos.receive_json()
    with c.websocket_connect("/ws") as otra:  # al cerrarse el primero se libera el cupo
        assert "turno" in otra.receive_json()


def test_autoarranque_espera_a_que_el_puerto_acepte_conexiones(monkeypatch):
    import asyncio

    import src.api.main as api

    class SimFalso:
        iniciado = None

        def iniciar(self, modo):
            SimFalso.iniciado = modo

    async def correr():
        srv = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        puerto = srv.sockets[0].getsockname()[1]
        srv.close()
        await srv.wait_closed()
        monkeypatch.setenv("SIM_URL", f"http://127.0.0.1:{puerto}")
        monkeypatch.setattr(api, "SIM", SimFalso())
        tarea = asyncio.create_task(api.autoarranque("3"))
        await asyncio.sleep(0.3)
        antes = SimFalso.iniciado                      # puerto cerrado: todavia no arranca
        srv2 = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", puerto)
        await asyncio.wait_for(tarea, 3)
        srv2.close()
        return antes, SimFalso.iniciado

    assert asyncio.run(correr()) == (None, "3")
