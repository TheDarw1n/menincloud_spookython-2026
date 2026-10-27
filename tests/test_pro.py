"""Tests del nivel PRO: capacidad de refugios (y, mas abajo, flota de rescate)."""
import asyncio
import os

from src.routing import capacidad
from src.routing.planner import Planner
from src.simulator.engine import Simulador
from src.world import zombies as zm
from src.world.graph import Grafo
from src.world.mundo import Mundo

G = Grafo.desde_archivo(os.environ["GRAPH_PATH"])
CALLADO = dict(log=lambda *a, **k: None)


def _grafo(calles, refugios):
    ids = sorted({a for a, _, _ in calles} | {b for _, b, _ in calles})
    return Grafo({"nodos": [{"id": n, "lat": 0, "lng": 0} for n in ids],
                  "calles": [{"id": f"E{i}", "de": a, "a": b, "distancia_m": d, "tipo": "calle"}
                             for i, (a, b, d) in enumerate(calles)],
                  "refugios": [{"id": n, "nodo": n} for n in refugios]})


def _cupo(rid, capacidad, ocupacion=0, evacua=0):
    return {"id": rid, "capacidad": capacidad, "ocupacion": ocupacion, "evacuaPorTurno": evacua}


def test_reparte_cuando_el_refugio_cercano_no_tiene_cupo():
    # a y b estan junto a R0 (cupo 1, no evacua); R1 queda lejos pero libre
    g = _grafo([("S1", "R0", 100), ("S2", "R0", 150), ("S1", "M", 500), ("S2", "M", 500), ("M", "R1", 500)],
               ["R0", "R1"])
    p = Planner(g, prediccion=False)
    p.actualizar({"turno": 1, "sobrevivientes": [{"id": "a", "nodo": "S1"}, {"id": "b", "nodo": "S2"}],
                  "refugios": [_cupo("R0", 1), _cupo("R1", 10)]})
    assert p._snap.asignacion == {"a": "R0", "b": "R1"}
    assert p.siguiente_nodo("S2", "b") == "M"       # va al refugio con cupo aunque R0 este al lado
    assert p.siguiente_nodo("S2", "otro") == "R0"   # alguien sin asignar va al mas cercano
    assert p.refugio_de("b", "S2") == "R1" and p.refugio_de("otro", "S2") == "R0"


def test_un_id_externo_igual_a_uno_propio_no_hereda_su_asignacion_ni_su_espera():
    from dataclasses import replace

    g = _grafo([("S1", "R0", 100), ("S2", "R0", 150), ("S1", "M", 500), ("S2", "M", 500), ("M", "R1", 500)],
               ["R0", "R1"])
    p = Planner(g, prediccion=False)
    p.actualizar({"turno": 1, "sobrevivientes": [{"id": "a", "nodo": "S1"}, {"id": "b", "nodo": "S2"}],
                  "refugios": [_cupo("R0", 1), _cupo("R1", 10)]})
    assert p.siguiente_nodo("S2", "b") == "M"      # el propio, en su nodo, sigue su asignacion (R1)
    assert p.siguiente_nodo("S1", "b") == "R0"     # el mismo id en OTRO nodo es un id externo
    assert p.refugio_de("b", "S1") == "R0"
    p._snap = replace(p._snap, esperar=frozenset({"a"}))
    assert p.siguiente_nodo("S1", "a") == "S1"     # el propio espera a su camioneta
    assert p.siguiente_nodo("S2", "a") == "R0"     # un externo con su id no se queda quieto


def test_cupo_proyectado_cuenta_la_evacuacion_desde_el_turno_siguiente():
    tablas = {"R0": {"A": 1.0, "B": 2.0}, "R1": {"A": 50.0, "B": 50.0}}
    saltos = {"R0": {"A": 1, "B": 2}, "R1": {"A": 5, "B": 5}}
    svs = [{"id": "a", "nodo": "A"}, {"id": "b", "nodo": "B"}]
    # R0 lleno y evacua 1 por turno: quien llega este turno (a, 1 calle) no entra; b llega en 2 y si
    asig, llenos = capacidad.asignar(tablas, saltos, svs, [_cupo("R0", 3, 3, 1), _cupo("R1", 9)])
    assert asig == {"a": "R1", "b": "R0"} and llenos == {"R0"}


def _sim(**kw):
    mundo = Mundo(G, Planner(G))

    async def directa(sid, nodo, turno):
        return mundo.planner.siguiente_nodo(nodo, sid)

    return mundo, Simulador(mundo, consulta=directa, turno_s=0, seed=5, **CALLADO, **kw)


def test_los_refugios_nunca_superan_su_cupo_y_se_publica_la_ocupacion():
    mundo, sim = _sim(turnos_ronda=60)
    sim._preparar(3)

    async def jugar():
        for _ in range(60):
            await sim.turno()
            for r in sim.s["refugios"].values():
                assert 0 <= r["ocupacion"] <= r["capacidad"]

    asyncio.run(jugar())
    pub = {r["id"]: r for r in mundo.estado["refugios"]}
    assert all({"capacidad", "ocupacion", "evacuaPorTurno", "nombre"} <= set(r) for r in pub.values())
    assert sum(r["evacua"] for r in sim.s["refugios"].values()) >= 4
    assert {s["refugio"] for s in mundo.estado["sobrevivientes"]} <= set(G.refugios)


def test_refugio_lleno_rechaza_y_luego_admite_tras_evacuar():
    _, sim = _sim(turnos_ronda=1)
    sim._preparar(1)
    sim.s["refugios"] = {"R-2": {"capacidad": 1, "evacua": 1, "ocupacion": 1}}
    assert not sim._admitir("R-2")
    sim.s["refugios"]["R-2"]["ocupacion"] -= sim.s["refugios"]["R-2"]["evacua"]
    assert sim._admitir("R-2") and sim._admitir("R-1")  # R-1 sin cupo definido: sin limite


def test_sin_capacidad_no_hay_cupos():
    mundo, sim = _sim(turnos_ronda=5, capacidad=False)
    asyncio.run(sim.correr(2))
    assert sim.s["refugios"] == {} and sim.resultados[-1]["rechazados"] == 0
    assert all("capacidad" not in r for r in mundo.estado["refugios"])


def test_camioneta_recoge_al_que_mas_ahorra_y_lo_hace_esperar():
    # linea R - A - B - C - D - E - F - G (cada calle 100 m)
    nodos = ["R", "A", "B", "C", "D", "E", "F", "G"]
    g = _grafo([(a, b, 100) for a, b in zip(nodos, nodos[1:])], ["R"])
    p = Planner(g, prediccion=False, capacidad=False)
    svs = [{"id": "lejos", "nodo": "G"}, {"id": "cerca", "nodo": "A"}]
    # desde el refugio no conviene: 4 turnos para llegar + 4 de vuelta > 7 caminando
    p.actualizar({"turno": 1, "sobrevivientes": svs, "camionetas": [{"id": "C-1", "nodo": "R", "pasajeros": 0}]})
    assert p.objetivos_flota()["C-1"] == {"tipo": "libre"} and not p.esperando("lejos")
    # con la camioneta en F si: 1 turno para llegar + 4 de vuelta = 2 turnos menos que caminar 7
    p.actualizar({"turno": 2, "sobrevivientes": svs, "camionetas": [{"id": "C-1", "nodo": "F", "pasajeros": 0}]})
    assert p.objetivos_flota()["C-1"] == {"tipo": "recoger", "sid": "lejos", "nodo": "G"}
    assert p.esperando("lejos") and p.siguiente_nodo("G", "lejos") == "G"   # llega el proximo turno: espera
    assert p.siguiente_nodo("A", "cerca") == "R"                             # a 1 calle: camina
    assert p.pasos_camioneta("C", "R") == ["B", "A"]                         # 2 calles por turno


def test_camioneta_con_pasajeros_entrega_en_refugio_con_cupo():
    g = _grafo([("X", "R0", 100), ("X", "M", 100), ("M", "R1", 300)], ["R0", "R1"])
    p = Planner(g, prediccion=False)
    p.actualizar({"turno": 1, "sobrevivientes": [],
                  "camionetas": [{"id": "C-1", "nodo": "X", "pasajeros": 3, "capacidad": 4}],
                  "refugios": [_cupo("R0", 4, 3), _cupo("R1", 10)]})  # R0 solo tiene 1 lugar
    assert p.objetivos_flota()["C-1"] == {"tipo": "entregar", "refugio": "R1", "nodo": "R1"}


def test_flota_en_una_ronda_rescata_sin_pasar_por_zombies_ni_perder_gente():
    mundo, sim = _sim(turnos_ronda=50)
    sim._preparar(3)

    async def jugar():
        for _ in range(50):
            antes = {c["id"]: c["nodo"] for c in sim.s["camionetas"]}
            await sim.turno()
            vetados = {z["nodo"] for z in sim.s["zombies"] if z["visible"]} | zm.zonas_horda(G, sim.s["zombies"])
            for c in sim.s["camionetas"]:
                assert len(c["pasajeros"]) <= c["capacidad"]
                assert c["nodo"] == antes[c["id"]] or c["nodo"] not in vetados  # nunca entra a un zombie/horda
            assert len(sim.s["sobrevivientes"]) + sim._a_bordo() == 200

    asyncio.run(jugar())
    cam = mundo.estado["camionetas"]
    assert len(cam) == 5 and all({"id", "nodo", "pasajeros", "capacidad", "estado", "ruta"} <= set(c) for c in cam)
    assert all(c["pasajeros"] or c["estado"] != "entregando" for c in cam)  # nadie "entrega" vacia
    assert sim.s["stats"]["en_camioneta"] > 0


def test_sin_flota_no_hay_camionetas():
    mundo, sim = _sim(turnos_ronda=3, flota=False)
    asyncio.run(sim.correr(1))
    assert sim.s["camionetas"] == [] and mundo.estado["camionetas"] == []


def test_lectura_literal_sin_refugios_fortificados(monkeypatch):
    import random

    from src.world import zombies as zmod
    monkeypatch.setattr(zmod, "FORTIFICADOS", False)
    assert zmod.zonas_horda(G, [{"tipo": "horda", "nodo": "N-0019"}]) >= {"N-0020"}  # la zona cubre el refugio
    caminante = {"id": "Z", "tipo": "caminante", "nodo": "N-0015", "previo": "N-0015", "visible": True,
                 "fase": 0, "pasos": []}
    entro = False
    for t in range(0, 200, 2):
        zmod.mover_todos(G, [caminante], frozenset(), set(), t, random.Random(t), zmod.nodos_vetados(G))
        entro |= caminante["nodo"] in G.nodos_refugio
    assert entro
    # con un zombie en el refugio, quien espera en la puerta huye y el refugio queda sin tabla
    p = Planner(G, prediccion=False, capacidad=False, flota=False)
    p.actualizar({"turno": 1, "zombies": [{"id": "Z", "tipo": "caminante", "nodo": "N-0020", "previo": "N-0015",
                                           "visible": True, "pasos": [["N-0015", "N-0020"]]}]})
    assert p._snap.tablas["R-1"] == {} and p.siguiente_nodo("N-0020", "S") == "N-0019"
