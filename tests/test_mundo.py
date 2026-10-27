import asyncio
import os
import random

from src.routing.planner import Planner
from src.simulator.engine import Simulador
from src.world import bites, zombies as zm
from src.world.graph import Grafo
from src.world.mundo import Mundo

G = Grafo.desde_archivo(os.environ["GRAPH_PATH"])  # grafo de prueba (tests/conftest.py)


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


def test_horda_muerde_en_su_nodo_y_en_todos_sus_vecinos():
    hordas = [z("H", "horda", "N-0007")]
    zonas = zm.zonas_horda(G, hordas)
    assert zonas == {"N-0007", "N-0002", "N-0006", "N-0008", "N-0012"}
    assert bites.mordidos({"A": ("N-0003", "N-0008")}, hordas, zonas) == {"A"}   # vecino de la horda
    assert bites.mordidos({"A": ("N-0003", "N-0004")}, hordas, zonas) == set()


def test_cruce_con_cualquiera_de_los_dos_pasos_del_corredor():
    zs = [z("Z", "corredor", "N-0003", previo="N-0001", pasos=[("N-0001", "N-0002"), ("N-0002", "N-0003")])]
    assert bites.mordidos({"A": ("N-0002", "N-0001")}, zs) == {"A"}   # cruza el primer paso
    assert bites.mordidos({"A": ("N-0003", "N-0002")}, zs) == {"A"}   # cruza el segundo paso
    assert bites.mordidos({"A": ("N-0007", "N-0007")}, zs) == set()   # quieto lejos: a salvo


def test_zombies_nunca_entran_a_un_refugio():
    rng = random.Random(7)
    zs = [z(f"Z{i}", "caminante", n) for i, n in enumerate(("N-0015", "N-0019", "N-0011", "N-0017"))]
    zs += [z("C", "corredor", "N-0018")]
    for t in range(1, 200):
        zm.mover_todos(G, zs, frozenset(), {"N-0014"}, t, rng, G.nodos_refugio)
        assert not {x["nodo"] for x in zs} & G.nodos_refugio


def test_evento_no_aisla_barrios_de_los_refugios():
    from src.world import events
    # N-0020 (refugio) solo tiene 2 calles: E-0027 y E-0031; cerrar ambas lo aislaria aunque sea la mas usada
    bloqueadas = ["E-0027"]
    ev = [(1, "puente")]
    ocurridos = events.aplicar(G, ev, 1, bloqueadas, random.Random(1), uso={"E-0031": 99})
    assert ocurridos and ocurridos[0]["arista"] != "E-0031" and "E-0031" not in bloqueadas
