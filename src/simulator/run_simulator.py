"""Corre rondas COMPLETAS en local, sin HTTP (consulta directa al planner), e imprime los
resultados y el puntaje de la rubrica. Util para depurar zombies/rutas rapido:
  TURNO_S=0 python -m src.simulator.run_simulator 3        (1, 2, 3 o ciclo)   [SEED=7 para repetir]
Para la prueba real (HTTP + mapa en vivo) usa la API: POST /ws/sim/iniciar."""
import asyncio
import json
import os
import sys

from ..routing.planner import Planner
from ..world.graph import Grafo
from ..world.mundo import Mundo
from .engine import Simulador


async def main(modo):
    g = Grafo.desde_archivo(os.environ.get("GRAPH_PATH", "data/manta_graph.json"))
    mundo = Mundo(g, Planner(g))

    async def consulta(sid, nodo, turno):
        return mundo.planner.siguiente_nodo(nodo, sid)

    sim = Simulador(mundo, consulta=consulta, turno_s=float(os.environ.get("TURNO_S", "0")),
                    turnos_ronda=int(os.environ.get("TURNOS_RONDA", "150")),
                    seed=int(os.environ["SEED"]) if os.environ.get("SEED") else None,
                    reponer=os.environ.get("SIM_POBLACION", "continua") != "fija",
                    log=lambda *a, **k: None)
    for ronda in ((1, 2, 3) if modo == "ciclo" else (int(modo),)):
        await sim.correr(ronda)
        print(json.dumps(sim.resultados[-1], indent=2, ensure_ascii=False))
    print(json.dumps({"puntaje": sim.puntaje()}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "1"))
