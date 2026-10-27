import asyncio
import os
import random

from src.routing import riesgo
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
            return mundo.planner.siguiente_nodo(nodo, sid)

        sim = Simulador(mundo, consulta=consulta, turno_s=0, turnos_ronda=45, seed=ronda, log=lambda *a, **k: None)
        asyncio.run(sim.correr(ronda))
        r = sim.resultados[-1]
        assert r["turnos"] == 45 and r["errores_o_timeout"] == 0
        assert len(mundo.estado["sobrevivientes"]) == {1: 20, 2: 80, 3: 200}[ronda]
        assert r["salvados"] + r["mordidos"] > 0
        assert 0 < r["eficiencia"] <= 1 and mundo.estado["corriendo"] is False
        assert mundo.estado["resultados"][-1]["ronda"] == ronda and mundo.estado["puntaje"]["rondas"] == [ronda]


def test_penalizacion_prefiere_ruta_con_margen():
    # Zombie en N-0008; ir por N-0007 (vecino) cuesta +30 s, asi que desde N-0006 conviene bajar por N-0011
    m = Mundo(G, Planner(G, prediccion=False))
    m.publicar_zombies(1, [z("Z", "caminante", "N-0008")], [])
    pen = riesgo.penalizacion(G, [z("Z", "caminante", "N-0008")], frozenset({"N-0008"}), frozenset(), prediccion=False)
    assert pen["N-0007"] == riesgo.P_VECINO
    assert m.planner.siguiente_nodo("N-0006") == "N-0011"


def _grafo(calles, refugios):
    ids = sorted({a for a, _, _ in calles} | {b for _, b, _ in calles})
    return Grafo({"nodos": [{"id": n, "lat": 0, "lng": 0} for n in ids],
                  "calles": [{"id": f"E{i}", "de": a, "a": b, "distancia_m": d, "tipo": "calle"}
                             for i, (a, b, d) in enumerate(calles)],
                  "refugios": [{"id": f"R{i}", "nodo": n} for i, n in enumerate(refugios)]})


def test_primer_paso_suma_la_calle_aunque_el_vecino_este_mas_cerca():
    # A-B mide 1000 m aunque B esta junto al refugio; A-C-R suma 900 m: conviene C
    g = _grafo([("A", "B", 1000), ("B", "R", 50), ("A", "C", 100), ("C", "R", 800)], ["R"])
    p = Planner(g)
    p.actualizar({"turno": 1})
    assert p.siguiente_nodo("A") == "C"


def test_primer_paso_suma_la_penalizacion_del_vecino():
    # B esta mas cerca del refugio pero junto a un zombie en X (+30 s); por C se llega antes y lejos de el
    g = _grafo([("A", "B", 100), ("A", "C", 100), ("B", "R", 100), ("C", "R", 200), ("B", "X", 100)], ["R"])
    p = Planner(g, prediccion=False)
    p.actualizar({"turno": 1, "zombies": [z("Z", "caminante", "X")]})
    assert p.siguiente_nodo("A") == "C"


def test_no_se_cruza_con_el_zombie_que_llego_por_esa_calle():
    # El zombie bajo de N-0006 a N-0001, donde esta el sobreviviente. Volver por N-0006 seria la
    # ruta mas barata, pero es cruzarse con el por la misma calle: debe huir por N-0002.
    m = Mundo(G, Planner(G))
    m.publicar_zombies(1, [z("Z", "caminante", "N-0001", previo="N-0006", pasos=[("N-0006", "N-0001")])], [])
    assert m.planner.siguiente_nodo("N-0001") == "N-0002"


def test_estado_publica_pasos_y_zonas_de_horda_y_no_cruza_otro_refugio():
    m = Mundo(G, Planner(G))
    corredor = z("C", "corredor", "N-0003", previo="N-0001", pasos=[("N-0001", "N-0002"), ("N-0002", "N-0003")])
    m.publicar_zombies(3, [z("H", "horda", "N-0007"), corredor], [])
    assert m.estado["zonasHorda"] == ["N-0002", "N-0006", "N-0007", "N-0008", "N-0012"]
    assert m.estado["zombies"][1]["pasos"] == [["N-0001", "N-0002"], ["N-0002", "N-0003"]]
    assert "N-0016" not in m.planner._snap.tablas["R-1"]  # hacia R-1 no se pasa por R-2
    assert m.planner.ruta("N-0014")[-1] in G.nodos_refugio


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


def test_prediccion_anticipa_la_persecucion_del_corredor():
    # corredor en N-0001 y sobreviviente en N-0004 (a 3 calles): el proximo turno pisara N-0002 y N-0003
    assert riesgo.predecir_corredor(G, "N-0001", {"N-0004"}, frozenset()) == ["N-0002", "N-0003"]
    assert riesgo.predecir_corredor(G, "N-0001", {"N-0020"}, frozenset()) == []  # nadie a <= 3: no persigue
    entra = riesgo.llegadas(G, [z("C", "corredor", "N-0001")], frozenset())
    assert entra["N-0002"] == {"N-0001"} and entra["N-0003"] == {"N-0002"} and "N-0004" not in entra


def test_trampa_donde_cae_un_corredor_y_no_queda_salida():
    # N-0005 (esquina) solo sale a N-0004 y N-0010. El corredor en N-0003 entra por N-0004 y un
    # caminante ocupa N-0010: si un sobreviviente queda en N-0005, el proximo turno no tiene salida.
    zs = [z("C", "corredor", "N-0003"), z("W", "caminante", "N-0010", previo="N-0015")]
    prohibidos = frozenset({"N-0003", "N-0010"})
    pen = riesgo.penalizacion(G, zs, prohibidos, frozenset())
    assert pen["N-0005"] == riesgo.P_TRAMPA[0]
    assert pen.get("N-0008", 0) == 0  # el corredor puede caer ahi pero quedan 2+ salidas libres


def test_caminante_que_acaba_de_moverse_no_amenaza_el_proximo_turno():
    assert riesgo.llegadas(G, [z("Z", "caminante", "N-0008", previo="N-0003")], frozenset()) == {}
    assert set(riesgo.llegadas(G, [z("Z", "caminante", "N-0008")], frozenset())) == {"N-0003", "N-0007", "N-0009", "N-0013"}
    sin_pred = riesgo.penalizacion(G, [z("Z", "caminante", "N-0008", previo="N-0003")], frozenset(), frozenset(),
                                   prediccion=False)
    assert sin_pred["N-0007"] == riesgo.P_VECINO
