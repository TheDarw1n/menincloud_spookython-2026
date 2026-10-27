import asyncio
import os

from src.routing.planner import Planner
from src.simulator import engine, puntaje
from src.simulator.engine import Simulador
from src.world.graph import Grafo
from src.world.mundo import Mundo

G = Grafo.desde_archivo(os.environ["GRAPH_PATH"])
CALLADO = dict(log=lambda *a, **k: None)


def test_notas_de_la_rubrica():
    assert [puntaje.nota_latencia(x) for x in (150, 151, 300, 500, 501)] == [10, 7, 7, 4, 0]
    assert [puntaje.nota_disponibilidad(x) for x in (0.49, 0.5, 1.99, 2, 4.99, 5)] == [10, 6, 6, 3, 3, 0]


def test_puntaje_pondera_rondas_y_componentes():
    res = {r: {"supervivencia": s, "eficiencia": 1.0, "consultas": 1000, "errores_o_timeout": 0}
           for r, s in ((1, 1.0), (2, 0.5), (3, 0.0))}
    nota = puntaje.calcular(res, {1: [10.0] * 10, 2: [20.0] * 10, 3: [400.0] * 10})
    # supervivencia (1*1 + 2*0.5 + 3*0) / 6 = 1/3 -> 3.33; p95 de todo = 400 ms -> 4
    assert nota["supervivencia"] == 3.33 and nota["eficiencia"] == 10 and nota["latencia"] == 4
    assert nota["total"] == round(0.5 * 3.33 + 0.2 * 10 + 0.15 * 4 + 0.15 * 10, 2) and nota["completo"]
    assert puntaje.calcular({}, {}) is None


def _sim(consulta=None, **kw):
    mundo = Mundo(G, Planner(G))

    async def directa(sid, nodo, turno):
        return mundo.planner.siguiente_nodo(nodo, sid)

    return mundo, Simulador(mundo, consulta=consulta or directa, turno_s=0, seed=3, **CALLADO, **kw)


def test_timeouts_cuentan_como_error_y_en_la_latencia(monkeypatch):
    monkeypatch.setattr(engine, "LIMITE_S", 0.01)

    async def lenta(sid, nodo, turno):
        await asyncio.sleep(0.05)
        return nodo

    _, sim = _sim(consulta=lenta, turnos_ronda=2)
    asyncio.run(sim.correr(1))
    r = sim.resultados[-1]
    assert r["errores_o_timeout"] == r["consultas"] == 40 and r["pct_errores"] == 100
    assert r["latencia_ms"]["p95"] >= 10


def test_poblacion_fija_no_repone_y_termina_cuando_no_queda_nadie():
    mundo, sim = _sim(turnos_ronda=150, reponer=False)
    asyncio.run(sim.correr(1))
    r = sim.resultados[-1]
    assert r["turnos"] < 150 and not mundo.estado["sobrevivientes"]
    assert r["salvados"] + r["mordidos"] == 20 and r["supervivencia"] == round(r["salvados"] / 20, 3)
    assert r["en_juego_al_final"] == 0 and r["supervivencia_cohorte"] == r["supervivencia"]


def test_ciclo_completo_da_puntaje_con_las_tres_rondas():
    mundo, sim = _sim(turnos_ronda=30)
    asyncio.run(sim._ciclo())
    nota = mundo.estado["puntaje"]
    assert nota["completo"] and 0 <= nota["total"] <= 10 and nota["latencia"] == 10
    assert [r["ronda"] for r in mundo.estado["resultados"]] == [1, 2, 3]
    r3 = sim.resultados[-1]  # continua: N siguen en juego al final y la cohorte los cuenta como no salvados
    assert r3["en_juego_al_final"] == 200 and r3["supervivencia_cohorte"] < r3["supervivencia"]


def test_eficiencia_se_mide_contra_el_minimo_de_calles():
    mundo, sim = _sim(turnos_ronda=1)
    sim._preparar(1)
    # N-0001 -> N-0006 -> N-0011 -> N-0016 (R-2): 3 calles; con E-0002 cerrada sale por N-0002: 5
    assert sim.optimo["N-0001"] == 3 and sim.optimo["N-0016"] == 0
    sim.s["bloqueadas"].append("E-0002")
    sim._calcular_optimo()
    assert sim.optimo["N-0001"] == 5


def test_dynamodb_lento_no_frena_el_turno():
    import time

    class Lento:
        habilitado = True
        llamadas = 0

        def guardar(self, turno, texto):
            Lento.llamadas += 1
            time.sleep(0.4)

        def guardar_resultado(self, ronda, texto):
            pass

    _, sim = _sim(turnos_ronda=12, snapshots=Lento(), snapshot_cada=2)

    async def jugar():
        sim._preparar(1)
        t0 = time.perf_counter()
        for _ in range(6):
            await sim.turno()
        return time.perf_counter() - t0

    assert asyncio.run(jugar()) < 0.4   # 6 turnos (3 snapshots) sin esperar a DynamoDB
    assert Lento.llamadas >= 1          # se intento guardar; los que encontraron uno en curso se omiten


def test_reanudar_juega_solo_los_turnos_que_faltaban():
    import json

    import pytest

    guardados = {}

    class Memoria:
        habilitado = True

        def guardar(self, turno, texto):
            guardados[turno] = texto

        def guardar_resultado(self, ronda, texto):
            pass

    _, sim = _sim(turnos_ronda=6, snapshots=Memoria(), snapshot_cada=2)

    async def jugar():  # 4 turnos como en _bucle
        sim._preparar(3)
        for _ in range(4):
            await sim.turno()
            sim.s["turnos_restantes"] -= 1
            await asyncio.sleep(0.05)  # deja terminar el guardado en segundo plano

    asyncio.run(jugar())
    foto = json.loads(guardados[4])
    assert foto["turno"] == 4 and foto["turnos_restantes"] == 2

    mundo2, sim2 = _sim(turnos_ronda=6)  # proceso nuevo: reanuda desde el snapshot

    async def reanudar():
        sim2.reanudar(foto)
        assert mundo2.estado["sobrevivientes"] and mundo2.estado["camionetas"]  # antes del 1er turno
        await sim2._tarea

    asyncio.run(reanudar())
    assert sim2.s["turno"] == 6 and sim2.resultados[-1]["turnos"] == 6
    with pytest.raises(RuntimeError):
        sim2.reanudar(dict(foto, turnos_restantes=0))  # ronda ya terminada


def test_al_terminar_la_ronda_no_quedan_turnos():
    for reponer in (True, False):  # con poblacion fija la ronda termina antes del ultimo turno
        mundo, sim = _sim(turnos_ronda=40, reponer=reponer)
        asyncio.run(sim.correr(1))
        assert mundo.estado["turnosRestantes"] == 0 and mundo.estado["metricas"]["turnosRestantes"] == 0


def test_los_sobrevivientes_nacen_en_los_barrios_del_enunciado():
    g = Grafo.desde_archivo("data/manta_graph.json")
    mundo = Mundo(g, Planner(g))
    sim = Simulador(mundo, consulta=None, turno_s=0, seed=1, **CALLADO)
    sim._preparar(3)
    barrios = {g.nodos[sv["nodo"]]["barrio"] for sv in sim.s["sobrevivientes"]}
    assert barrios <= {"tarqui", "los-esteros", "barbasquillo", "jocay"} and len(barrios) == 4


def test_ninguna_mordida_era_evitable_en_rondas_completas(monkeypatch):
    """Para cada mordido se revisa, con las reglas reales del simulador, si habia una jugada
    segura (quedarse o ir a un vecino por calle abierta sin zombie, sin zona de horda y sin
    cruzarse). Si la habia, el planner fallo."""
    from src.simulator import engine as eng
    from src.world import bites as mordidas

    g = Grafo.desde_archivo("data/manta_graph.json")
    evitables, total = [], [0]
    original = mordidas.mordidos

    for ronda in (1, 2, 3):  # rondas de 150 turnos, con todos sus eventos de ciudad
        mundo = Mundo(g, Planner(g))

        async def directa(sid, nodo, turno, mundo=mundo):
            return mundo.planner.siguiente_nodo(nodo, sid)

        sim = Simulador(mundo, consulta=directa, turno_s=0, seed=ronda, **CALLADO)

        def espia(mov, zombies, zonas=frozenset(), sim=sim):
            muertos = original(mov, zombies, zonas)
            letal = {z["nodo"] for z in zombies} | set(zonas)
            pasos = {(a, b) for z in zombies for a, b in z.get("pasos", [])}
            bloq = set(sim.s["bloqueadas"])
            for sid in muertos:
                prev, _ = mov[sid]
                opciones = [prev] + [v for v, c, _ in g.vecinos[prev] if c not in bloq]
                if any(v not in letal and not (v != prev and (v, prev) in pasos) for v in opciones):
                    evitables.append((ronda, sid, prev))
            total[0] += len(muertos)
            return muertos

        monkeypatch.setattr(eng.bites, "mordidos", espia)
        asyncio.run(sim.correr(ronda))
        assert sim.s["turno"] == 150 and len(sim.s["log_eventos"]) == ronda - 1
    assert total[0] > 0 and evitables == []


def test_los_eventos_ocurren_en_ambos_modos_de_poblacion():
    g = Grafo.desde_archivo("data/manta_graph.json")
    for reponer in (True, False):
        for ronda, esperados in ((2, ["puente"]), (3, ["avenida", "avenida"])):
            mundo = Mundo(g, Planner(g))

            async def directa(sid, nodo, turno, mundo=mundo):
                return mundo.planner.siguiente_nodo(nodo, sid)

            sim = Simulador(mundo, consulta=directa, turno_s=0, seed=ronda, reponer=reponer, **CALLADO)
            asyncio.run(sim.correr(ronda))
            assert [e["tipo"] for e in sim.s["log_eventos"]] == esperados, (reponer, ronda)
            assert len(sim.s["bloqueadas"]) == len(esperados)
