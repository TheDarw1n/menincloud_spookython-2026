"""A/B del planner: corre rondas completas SIN HTTP (consulta directa al planner) con distintas
variantes y semillas, e imprime supervivencia, eficiencia, mordidas, rescates en camioneta,
rechazos y la parte de supervivencia + eficiencia del puntaje (maximo 7 de 10, ponderada como la
rubrica). Todas las decisiones de diseno del README salen de aqui.

  python tools/ab_planner.py --rondas 2,3 --semillas 6 \\
      "todo:" "sin_prediccion:pred=0" "sin_capacidad:cap=0" "sin_flota:flota=0" "sin_cruce:cruce=0"

Claves de cada variante (por defecto todo activo, como en produccion): pred, cap, flota (0/1),
cruce (segundos por interseccion), evac y cuello (cupos de refugios)."""
import argparse
import asyncio
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.routing.planner import Planner  # noqa: E402
from src.simulator import engine, puntaje  # noqa: E402
from src.simulator.engine import Simulador  # noqa: E402
from src.world import graph  # noqa: E402
from src.world.mundo import Mundo  # noqa: E402

BASE = dict(cruce=graph.CRUCE_S, evac=engine.EVAC_FACTOR, cuello=engine.CUELLO)


def correr(ruta_grafo, ronda, seed, cfg):
    graph.CRUCE_S = float(cfg.get("cruce", BASE["cruce"]))
    engine.EVAC_FACTOR = float(cfg.get("evac", BASE["evac"]))
    engine.CUELLO = float(cfg.get("cuello", BASE["cuello"]))
    pred, cap, flota = (cfg.get(k, "1") != "0" for k in ("pred", "cap", "flota"))
    g = graph.Grafo.desde_archivo(ruta_grafo)
    mundo = Mundo(g, Planner(g, prediccion=pred, capacidad=cap, flota=flota))

    async def consulta(sid, nodo, turno):
        return mundo.planner.siguiente_nodo(nodo, sid)

    sim = Simulador(mundo, consulta=consulta, turno_s=0, turnos_ronda=150, seed=seed,
                    capacidad=cap, flota=flota, log=lambda *a, **k: None)
    asyncio.run(sim.correr(ronda))
    return sim.resultados[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("variantes", nargs="+", help='"nombre:clave=valor,..." (ej. "sin_flota:flota=0")')
    ap.add_argument("--grafo", default="data/manta_graph.json")
    ap.add_argument("--rondas", default="1,2,3")
    ap.add_argument("--semillas", type=int, default=4)
    a = ap.parse_args()
    rondas = [int(r) for r in a.rondas.split(",")]
    for spec in a.variantes:
        nombre, _, kv = spec.partition(":")
        cfg = dict(x.split("=") for x in kv.split(",") if x)
        partes, nota = [], 0.0
        for ronda in rondas:
            res = [correr(a.grafo, ronda, s, cfg) for s in range(a.semillas)]
            sup = statistics.mean(r["supervivencia"] for r in res)
            ef = statistics.mean(r["eficiencia"] for r in res)
            partes.append(f"R{ronda} sup={sup:.4f} ef={ef:.3f} mord={sum(r['mordidos'] for r in res)} "
                          f"cam={sum(r['rescatados_en_camioneta'] for r in res)} rech={sum(r['rechazados'] for r in res)}")
            nota += puntaje.PESO_RONDA[ronda] * (0.5 * 10 * sup + 0.2 * 10 * ef)
        nota /= sum(puntaje.PESO_RONDA[r] for r in rondas)
        print(f"{nombre:16} | " + " | ".join(partes) + f" | sup+ef={nota:.3f}/7", flush=True)


if __name__ == "__main__":
    main()
