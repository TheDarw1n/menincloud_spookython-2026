import asyncio
import random

from src.routing.planner import Planner
from src.simulator.engine import Simulador
from src.world import bites, zombies as zm
from src.world.graph import Grafo
from src.world.mundo import Mundo

G = Grafo.desde_archivo("data/manta_graph.json")


def z(id, tipo, nodo, previo=None, pasos=(), visible=True):
    return {"id": id, "tipo": tipo, "nodo": nodo, "previo": previo or nodo,
            "visible": visible, "fase": 0, "pasos": [list(p) for p in pasos]}


def test_mordida_mismo_nodo_y_cruce():
    zs = [z("Z1", "caminante", "N-0003", pasos=[("N-0002", "N-0003")])]
    assert bites.mordidos({"A": ("N-0004", "N-0003")}, zs) == {"A"}           # mismo nodo
    zs = [z("Z1", "caminante", "N-0001", pasos=[("N-0002", "N-0001")])]
    assert bites.mordidos({"A": ("N-0001", "N-0002")}, zs) == {"A"}           # se cruzan
    assert bites.mordidos({"A": ("N-0006", "N-0007")}, zs) == set()           # a salvo


def test_planner_evita_zombie_visible_y_vecinos_de_horda():
    m = Mundo(G, Planner(G))
    m.publicar_zombies(1, [z("Z", "caminante", "N-0006")], [])
    assert m.planner.siguiente_nodo("N-0001") == "N-0002"
    m.publicar_zombies(2, [z("H", "horda", "N-0007")], [])  # vecinos de N-0007 prohibidos
    assert m.planner.siguiente_nodo("N-0006") not in ("N-0002", "N-0008", "N-0012", "N-0007")


def test_zombie_dormido_despierta_y_es_invisible_antes():
    zs = [z("Z", "dormido", "N-0009", visible=False)]
    zm.mover_todos(G, zs, frozenset(), {"N-0001"}, 1, random.Random(1))
    assert zs[0]["visible"] is False
    zm.mover_todos(G, zs, frozenset(), {"N-0008"}, 2, random.Random(1))
    assert zs[0]["tipo"] == "caminante" and zs[0]["visible"] is True


def test_corredor_persigue_y_avanza_dos():
    zs = [z("Z", "corredor", "N-0001")]
    zm.mover_todos(G, zs, frozenset(), {"N-0003"}, 1, random.Random(1))
    assert zs[0]["nodo"] == "N-0003" and len(zs[0]["pasos"]) == 2


def test_rondas_completas_sin_romper():
    for ronda in (1, 2, 3):
        mundo = Mundo(G, Planner(G))

        async def consulta(sid, nodo, turno, mundo=mundo):
            return mundo.planner.siguiente_nodo(nodo)

        sim = Simulador(mundo, consulta=consulta, turno_s=0, turnos_ronda=45, seed=ronda)
        asyncio.run(sim.correr(ronda))
        r = sim.resultados[-1]
        assert r["turnos"] == 45 and r["errores_o_timeout"] == 0
        assert len(mundo.estado["sobrevivientes"]) == {1: 20, 2: 80, 3: 200}[ronda]
        assert r["salvados"] + r["mordidos"] > 0


def test_penalizacion_prefiere_ruta_con_margen():
    # Zombie en N-0008; ir por N-0007 (vecino) cuesta +30 s, asi que desde N-0006 conviene bajar por N-0011
    m = Mundo(G, Planner(G))
    m.publicar_zombies(1, [z("Z", "caminante", "N-0008")], [])
    assert m.penalizados([z("Z", "caminante", "N-0008")], frozenset())["N-0007"] == 30.0
    assert m.planner.siguiente_nodo("N-0006") == "N-0011"
