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
