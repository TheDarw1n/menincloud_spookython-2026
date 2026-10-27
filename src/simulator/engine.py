"""Simulador del apocalipsis. Cada turno: (1) zombies se mueven, (2) se publica el mundo
(el planner se recalcula UNA vez), (3) cada sobreviviente consulta POST /paso, (4) mordidas."""
import asyncio
import os
import random
import time

import httpx

from ..world import bites, events, zombies as zm

# Fracciones de zombies respecto al numero de nodos; eventos = (turno, tipo de calle)
RONDAS = {
    1: dict(sobrevivientes=20, zombies={"caminante": 0.05}, eventos=[]),
    2: dict(sobrevivientes=80, zombies={"caminante": 0.06, "corredor": 0.03, "horda": 0.015},
            eventos=[(60, "puente")]),
    3: dict(sobrevivientes=200, zombies={"caminante": 0.06, "corredor": 0.04, "horda": 0.02, "dormido": 0.05},
            eventos=[(40, "avenida"), (90, "avenida")]),
}
LIMITE_S = 0.5  # /paso debe responder en < 500 ms; si no, el sobreviviente se queda quieto


class Simulador:
    def __init__(self, mundo, consulta=None, turno_s=2.0, turnos_ronda=150, snapshots=None,
                 snapshot_cada=10, ruta_max=25, seed=None):
        self.mundo, self.grafo = mundo, mundo.grafo
        self.consulta = consulta or self._consulta_http
        self.turno_s, self.turnos_ronda = turno_s, turnos_ronda
        self.snapshots, self.snapshot_cada, self.ruta_max = snapshots, snapshot_cada, ruta_max
        self.rng = random.Random(seed)
        self.refugio_nodos = set(self.grafo.refugios.values())
        self.s = None
        self.lat, self.errores, self.consultas = [], 0, 0
        self.resultados = []
        self._tarea = None
        self._cliente = None

    # ---------- control ----------
    @property
    def corriendo(self):
        return self._tarea is not None and not self._tarea.done()

    def iniciar(self, modo):
        if self.corriendo:
            raise RuntimeError("ya hay una ronda en curso")
        if modo == "ciclo":
            self._tarea = asyncio.create_task(self._ciclo())
        elif modo in ("1", "2", "3"):
            self._tarea = asyncio.create_task(self.correr(int(modo)))
        else:
            raise ValueError("modo invalido: 1, 2, 3 o ciclo")

    def reanudar(self, snap):
        if self.corriendo:
            raise RuntimeError("ya hay una ronda en curso")
        self.s = snap
        self._reset_metricas()
        self._tarea = asyncio.create_task(self._bucle())

    async def detener(self):
        if self.corriendo:
            self._tarea.cancel()
            await asyncio.gather(self._tarea, return_exceptions=True)
        if self._cliente:
            await self._cliente.aclose()
            self._cliente = None

    async def _ciclo(self):
        for r in (1, 2, 3):
            await self.correr(r)

    async def correr(self, ronda):
        self._preparar(ronda)
        await self._bucle()

    # ---------- ronda ----------
    def _reset_metricas(self):
        self.lat, self.errores, self.consultas = [], 0, 0

    def _preparar(self, ronda):
        cfg = RONDAS[ronda]
        self._reset_metricas()
        self.s = {"ronda": ronda, "turno": 0, "turnos_restantes": self.turnos_ronda,
                  "zombies": zm_crear(self, cfg), "bloqueadas": [],
                  "eventos": [list(e) for e in cfg["eventos"]], "seq": 0,
                  "sobrevivientes": [], "stats": {"salvados": 0, "mordidos": 0, "turnos_salvado": 0}}
        self.s["sobrevivientes"] = [self._nuevo() for _ in range(cfg["sobrevivientes"])]

    def _nuevo(self):
        s = self.s
        ocupados = {z["nodo"] for z in s["zombies"]} | self.refugio_nodos
        libres = [n for n in self.grafo.nodos if n not in ocupados] or list(self.grafo.nodos)
        s["seq"] += 1
        return {"id": f"S-{s['seq']:04d}", "nodo": self.rng.choice(libres), "turno_inicio": s["turno"]}

    async def _bucle(self):
        s = self.s
        while s["turnos_restantes"] > 0:
            t0 = time.monotonic()
            await self.turno()
            s["turnos_restantes"] -= 1
            await asyncio.sleep(max(0.0, self.turno_s - (time.monotonic() - t0)))
        await self._finalizar()

    def _valido(self, nodo, nuevo, bloq):
        return isinstance(nuevo, str) and (nuevo == nodo or self.grafo.hay_calle(nodo, nuevo, bloq))

    async def _consultar(self, sv, turno):
        self.consultas += 1
        t0 = time.perf_counter()
        try:
            nuevo = await asyncio.wait_for(self.consulta(sv["id"], sv["nodo"], turno), LIMITE_S)
        except Exception:
            self.errores += 1
            return sv["nodo"]
        if len(self.lat) < 50000:
            self.lat.append((time.perf_counter() - t0) * 1000)
        return nuevo

    async def turno(self):
        s = self.s
        s["turno"] += 1
        t = s["turno"]
        events.aplicar(self.grafo, s["eventos"], t, s["bloqueadas"], self.rng)
        bloq = frozenset(s["bloqueadas"])
        zm_mover = {sv["nodo"] for sv in s["sobrevivientes"]}
        zm.mover_todos(self.grafo, s["zombies"], bloq, zm_mover, t, self.rng)
        self.mundo.publicar_zombies(t, s["zombies"], s["bloqueadas"])

        vivos = s["sobrevivientes"]
        resp = await asyncio.gather(*(self._consultar(sv, t) for sv in vivos))
        mov = {}
        for sv, nuevo in zip(vivos, resp):
            mov[sv["id"]] = (sv["nodo"], nuevo if self._valido(sv["nodo"], nuevo, bloq) else sv["nodo"])
        muertos = bites.mordidos(mov, s["zombies"])

        siguientes, st = [], s["stats"]
        for sv in vivos:
            sv["nodo"] = mov[sv["id"]][1]
            if sv["id"] in muertos:
                st["mordidos"] += 1
                siguientes.append(self._nuevo())
            elif sv["nodo"] in self.refugio_nodos:
                st["salvados"] += 1
                st["turnos_salvado"] += t - sv["turno_inicio"]
                siguientes.append(self._nuevo())
            else:
                siguientes.append(sv)
        s["sobrevivientes"] = siguientes
        self.mundo.publicar_sobrevivientes(
            [{"id": sv["id"], "nodo": sv["nodo"], "ruta": self.mundo.planner.ruta(sv["nodo"], self.ruta_max)}
             for sv in siguientes],
            s["ronda"],
            {"salvados": st["salvados"], "mordidos": st["mordidos"],
             "turnosRestantes": s["turnos_restantes"] - 1})
        if self.snapshots and self.snapshots.habilitado and t % self.snapshot_cada == 0:
            try:
                await asyncio.to_thread(self.snapshots.guardar, t, self.exportar())
            except Exception as e:  # un fallo de DynamoDB no debe romper el juego
                print("snapshot fallo:", e)

    def exportar(self):
        s = self.s
        return {**s, "zombies": [dict(z) for z in s["zombies"]],
                "sobrevivientes": [dict(sv) for sv in s["sobrevivientes"]]}

    async def _finalizar(self):
        s, st = self.s, self.s["stats"]
        lat = sorted(self.lat)
        pct = lambda p: round(lat[min(len(lat) - 1, int(len(lat) * p))], 2) if lat else None
        total = st["salvados"] + st["mordidos"]
        res = {"ronda": s["ronda"], "turnos": s["turno"], "salvados": st["salvados"],
               "mordidos": st["mordidos"],
               "supervivencia": round(st["salvados"] / total, 3) if total else None,
               "turnos_promedio_por_rescate": round(st["turnos_salvado"] / st["salvados"], 2) if st["salvados"] else None,
               "consultas": self.consultas, "errores_o_timeout": self.errores,
               "pct_errores": round(100 * self.errores / self.consultas, 3) if self.consultas else 0,
               "latencia_ms": {"p50": pct(0.5), "p95": pct(0.95), "max": round(lat[-1], 2) if lat else None},
               "fin": int(time.time())}
        self.resultados.append(res)
        if self.snapshots and self.snapshots.habilitado:
            try:
                await asyncio.to_thread(self.snapshots.guardar_resultado, s["ronda"], res)
            except Exception as e:
                print("resultado no guardado:", e)

    async def _consulta_http(self, sid, nodo, turno):
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(
                base_url=os.environ.get("SIM_URL", "http://127.0.0.1:8000"),
                headers={"x-api-key": os.environ.get("API_KEY", "")},
                timeout=LIMITE_S, limits=httpx.Limits(max_connections=250))
        r = await self._cliente.post("/paso", json={"sobrevivienteId": sid, "nodoActual": nodo, "turno": turno})
        r.raise_for_status()
        return r.json()["siguienteNodo"]


def zm_crear(sim, cfg):
    return zm.crear(sim.grafo, cfg["zombies"], sim.rng, excluir=sim.refugio_nodos)
