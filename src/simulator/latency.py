"""Prueba de carga de POST /paso con concurrencia real y nodos distintos.
Uso: python -m src.simulator.latency URL API_KEY [--niveles 20,80,200] [--turnos 10] [--intervalo 0]
Para separar red de servidor, correrlo tambien desde CloudShell en us-east-1."""
import argparse
import asyncio
import json
import random
import time

import httpx

from .puntaje import nota_disponibilidad as puntaje_disponibilidad, nota_latencia as puntaje_latencia

LIMITE_MS = 500


async def un_turno(cli, nodos, n, turno):
    elegidos = random.sample(nodos, n) if n <= len(nodos) else random.choices(nodos, k=n)

    async def una(i, nodo):
        t0 = time.perf_counter()
        try:
            r = await cli.post("/paso", json={"sobrevivienteId": f"S-{i:04d}", "nodoActual": nodo, "turno": turno})
            ok = r.status_code == 200
        except Exception:
            ok = False
        ms = (time.perf_counter() - t0) * 1000
        return ms, ok and ms <= LIMITE_MS

    return await asyncio.gather(*(una(i, nd) for i, nd in enumerate(elegidos)))


async def nivel(url, key, nodos, n, turnos, intervalo):
    lims = httpx.Limits(max_connections=n + 10)
    async with httpx.AsyncClient(base_url=url, headers={"x-api-key": key}, timeout=2, limits=lims) as cli:
        tiempos, fallos, total = [], 0, 0
        for t in range(1, turnos + 1):
            ini = time.monotonic()
            for ms, ok in await un_turno(cli, nodos, n, t):
                tiempos.append(ms)
                total += 1
                fallos += 0 if ok else 1
            await asyncio.sleep(max(0, intervalo - (time.monotonic() - ini)))
    tiempos.sort()
    p = lambda q: tiempos[min(len(tiempos) - 1, int(len(tiempos) * q))]
    pct = 100 * fallos / total
    print(f"{n:>4} concurrentes x {turnos} turnos | p50={p(.5):.1f} p95={p(.95):.1f} p99={p(.99):.1f} "
          f"max={tiempos[-1]:.1f} ms | errores/fuera de tiempo={pct:.2f}% | "
          f"puntaje latencia={puntaje_latencia(p(.95))} disponibilidad={puntaje_disponibilidad(pct)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("key")
    ap.add_argument("--niveles", default="20,80,200")
    ap.add_argument("--turnos", type=int, default=10)
    ap.add_argument("--intervalo", type=float, default=0.0, help="segundos entre turnos (2 = ritmo real)")
    ap.add_argument("--grafo", default="data/manta_graph.json")
    a = ap.parse_args()
    nodos = [n["id"] for n in json.load(open(a.grafo, encoding="utf-8"))["nodos"]]
    for n in (int(x) for x in a.niveles.split(",")):
        asyncio.run(nivel(a.url.rstrip("/"), a.key, nodos, n, a.turnos, a.intervalo))


if __name__ == "__main__":
    main()
