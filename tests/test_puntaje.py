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


def test_ciclo_completo_da_puntaje_con_las_tres_rondas():
    mundo, sim = _sim(turnos_ronda=30)
    asyncio.run(sim._ciclo())
    nota = mundo.estado["puntaje"]
    assert nota["completo"] and 0 <= nota["total"] <= 10 and nota["latencia"] == 10
    assert [r["ronda"] for r in mundo.estado["resultados"]] == [1, 2, 3]


def test_eficiencia_se_mide_contra_el_minimo_de_calles():
    mundo, sim = _sim(turnos_ronda=1)
    sim._preparar(1)
    # N-0001 -> N-0006 -> N-0011 -> N-0016 (R-2): 3 calles; con E-0002 cerrada sale por N-0002: 5
    assert sim.optimo["N-0001"] == 3 and sim.optimo["N-0016"] == 0
    sim.s["bloqueadas"].append("E-0002")
    sim._calcular_optimo()
    assert sim.optimo["N-0001"] == 5
