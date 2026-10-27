"""Simulador del apocalipsis. Cada turno (2 s): (1) eventos de ciudad, (2) se mueven los
zombies, (3) se publica el mundo y el planner se recalcula UNA vez, (4) cada sobreviviente
consulta POST /paso (500 ms o se queda quieto), (5) mordidas, (6) llegadas a refugios,
(7) se reponen sobrevivientes y se publican el turno y las metricas de la rubrica."""
import asyncio
import json
from collections import Counter, deque
import os
import random
import time

import httpx

from ..world import bites, events, zombies as zm
from . import puntaje

# Fracciones de zombies respecto al numero de nodos; eventos = (turno, tipo de calle)
RONDAS = {
    1: dict(nombre="Anochecer", sobrevivientes=20, zombies={"caminante": 0.05}, eventos=[]),
    2: dict(nombre="Medianoche", sobrevivientes=80,
            zombies={"caminante": 0.06, "corredor": 0.03, "horda": 0.015}, eventos=[(40, "puente")]),
    3: dict(nombre="Apocalipsis", sobrevivientes=200,
            zombies={"caminante": 0.06, "corredor": 0.04, "horda": 0.02, "dormido": 0.05},
            eventos=[(30, "avenida"), (75, "avenida")]),
}
LIMITE_S = 0.5  # /paso debe responder en < 500 ms; si no, el sobreviviente se queda quieto
MAX_MUESTRAS = 100_000
# PRO capacidad: cada refugio evacua E personas por turno hacia la zona segura y tiene cupo para
# BUFFER_TURNOS turnos de su evacuacion. La evacuacion total cubre EVAC_FACTOR veces las llegadas
# esperadas, repartida segun la demanda de cada refugio; el de mayor demanda queda chico (CUELLO):
# si todos van al mas cercano se llena, asi que el planner tiene que repartir.
EVAC_FACTOR, CUELLO, BUFFER_TURNOS = 1.6, 0.45, 4


def log_json(evento, **datos):
    """Una linea JSON por evento en stdout -> CloudWatch Logs (filtros de metricas, ver README)."""
    print(json.dumps({"evento": evento, **datos}, ensure_ascii=False), flush=True)


class Simulador:
    def __init__(self, mundo, consulta=None, turno_s=2.0, turnos_ronda=150, snapshots=None,
                 snapshot_cada=10, ruta_max=25, seed=None, reponer=True, capacidad=True, log=log_json):
        self.mundo, self.grafo = mundo, mundo.grafo
        self.consulta = consulta or self._consulta_http
        self.turno_s, self.turnos_ronda = turno_s, turnos_ronda
        self.snapshots, self.snapshot_cada, self.ruta_max = snapshots, snapshot_cada, ruta_max
        self.reponer = reponer  # True: N sobrevivientes a la vez toda la ronda; False: poblacion fija
        self.capacidad = capacidad  # PRO: refugios con cupo y evacuacion
        self.log = log
        self.rng = random.Random(seed)
        self.s = None
        self.lat, self.errores, self.consultas = [], 0, 0
        self.resultados = []                    # historial de rondas terminadas
        self.ultimos, self.lat_rondas = {}, {}  # ultima corrida de cada ronda (para el puntaje)
        self.optimo = {}                        # nodo -> calles de la ruta mas corta sin zombies
        self.cercano = {}                       # nodo -> refugio con menos calles
        self._nodos_spawn = list(self.grafo.nodos)
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
        self.s = self._normalizar(snap)
        self._reset_metricas()
        self._calcular_optimo()
        self._tarea = asyncio.create_task(self._bucle())

    async def detener(self):
        if self.corriendo:
            self._tarea.cancel()
            await asyncio.gather(self._tarea, return_exceptions=True)
            self.mundo.publicar(corriendo=False)
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
                  "poblacion": cfg["sobrevivientes"],
                  "zombies": zm.crear(self.grafo, cfg["zombies"], self.rng, excluir=self.grafo.nodos_refugio),
                  "bloqueadas": [], "eventos": [list(e) for e in cfg["eventos"]], "log_eventos": [],
                  "seq": 0, "sobrevivientes": [], "refugios": {},
                  "stats": {"salvados": 0, "mordidos": 0, "rechazados": 0, "turnos_salvado": 0,
                            "ef_suma": 0.0, "ef_n": 0}}
        self._calcular_optimo()
        self.s["refugios"] = self._cupos(cfg["sobrevivientes"])
        self.s["sobrevivientes"] = self._nuevos(cfg["sobrevivientes"])
        # turno 0: el mapa muestra la ronda antes del primer movimiento
        self.mundo.publicar_zombies(0, self.s["zombies"], [], ronda=ronda, corriendo=True,
                                    turnosRestantes=self.turnos_ronda, eventos=[], refugios=self._pub_refugios())
        self._publicar_turno()

    def _cupos(self, n):
        """{refugio: cupo, evacuacion por turno y ocupacion} para N sobrevivientes a la vez.
        Llegadas esperadas por turno = N / viaje promedio (1.2 x el minimo de calles desde donde
        nacen); demanda de cada refugio = parte de esos nodos que le queda mas cerca."""
        if not self.capacidad:
            return {}
        nodos = [x for x in self._nodos_spawn if self.optimo.get(x)]
        if not nodos:
            return {}
        viaje = max(1.0, 1.2 * sum(self.optimo[x] for x in nodos) / len(nodos))
        demanda = Counter(self.cercano[x] for x in nodos)
        mayor = max(demanda, key=demanda.get)
        cupos = {}
        for rid in sorted(self.grafo.refugios):
            parte = demanda.get(rid, 0) / len(nodos)
            e = max(1, round(EVAC_FACTOR * n / viaje * parte * (CUELLO if rid == mayor else 1.0)))
            cupos[rid] = {"capacidad": e * BUFFER_TURNOS, "evacua": e, "ocupacion": 0}
        return cupos

    def _pub_refugios(self):
        g, cupos = self.grafo, self.s["refugios"]
        pub = []
        for rid, nodo in g.refugios.items():
            r = {"id": rid, "nodo": nodo, "nombre": g.info_refugios[rid].get("nombre", rid)}
            if rid in cupos:
                c = cupos[rid]
                r.update(capacidad=c["capacidad"], ocupacion=c["ocupacion"], evacuaPorTurno=c["evacua"])
            pub.append(r)
        return pub

    @staticmethod
    def _normalizar(snap):
        """Acepta snapshots de versiones anteriores (campos que faltan)."""
        s = dict(snap)
        s.setdefault("poblacion", RONDAS[s["ronda"]]["sobrevivientes"])
        s.setdefault("log_eventos", [])
        s.setdefault("refugios", {})
        st = dict(s.get("stats", {}))
        for k, v in (("salvados", 0), ("mordidos", 0), ("rechazados", 0), ("turnos_salvado", 0),
                     ("ef_suma", 0.0), ("ef_n", 0)):
            st.setdefault(k, v)
        s["stats"] = st
        return s

    def _calcular_optimo(self):
        """Base de la eficiencia de la rubrica, en su lectura mas estricta: el MINIMO de calles
        (= turnos) hasta el refugio mas cercano, sin zombies y con las calles cerradas de ese
        momento (BFS desde los 4 refugios). El planner minimiza tiempo real, asi que sin zombies
        su eficiencia contra esta base queda apenas bajo 1."""
        g, bloq = self.grafo, frozenset(self.s["bloqueadas"])
        self.optimo = dict.fromkeys(g.nodos_refugio, 0)
        self.cercano = dict(g.refugio_de_nodo)  # nodo -> refugio con menos calles
        cola = deque(g.nodos_refugio)
        while cola:
            u = cola.popleft()
            for v, c, _ in g.vecinos[u]:
                if c not in bloq and v not in self.optimo:
                    self.optimo[v] = self.optimo[u] + 1
                    self.cercano[v] = self.cercano[u]
                    cola.append(v)

    def _nuevos(self, k):
        """k sobrevivientes nuevos lejos de zombies (nadie nace pegado a uno ni en una zona de horda)."""
        if k <= 0:
            return []
        s, g = self.s, self.grafo
        vetados = {z["nodo"] for z in s["zombies"]} | zm.zonas_horda(g, s["zombies"]) | g.nodos_refugio
        vetados |= {v for z in s["zombies"] if z["visible"] for v, _, _ in g.vecinos[z["nodo"]]}
        libres = ([n for n in self._nodos_spawn if n not in vetados]
                  or [n for n in g.nodos if n not in vetados] or list(g.nodos))
        nuevos = []
        for _ in range(k):
            s["seq"] += 1
            nodo = self.rng.choice(libres)
            nuevos.append({"id": f"S-{s['seq']:04d}", "nodo": nodo, "turno_inicio": s["turno"],
                           "optimo": self.optimo.get(nodo)})
        return nuevos

    async def _bucle(self):
        s = self.s
        while s["turnos_restantes"] > 0:
            t0 = time.monotonic()
            await self.turno()
            s["turnos_restantes"] -= 1
            if not self.reponer and not s["sobrevivientes"]:
                break  # poblacion fija: ya no queda nadie en la calle
            await asyncio.sleep(max(0.0, self.turno_s - (time.monotonic() - t0)))
        await self._finalizar()

    def _valido(self, nodo, nuevo, bloq):
        return isinstance(nuevo, str) and (nuevo == nodo or self.grafo.hay_calle(nodo, nuevo, bloq))

    async def _consultar(self, sv, turno):
        self.consultas += 1
        t0 = time.perf_counter()
        try:
            nuevo = await asyncio.wait_for(self.consulta(sv["id"], sv["nodo"], turno), LIMITE_S)
        except Exception:  # error HTTP, cuerpo invalido o timeout
            nuevo = None
        ms = (time.perf_counter() - t0) * 1000
        if len(self.lat) < MAX_MUESTRAS:
            self.lat.append(ms)  # los timeouts tambien cuentan para el p95
        if nuevo is None or ms > LIMITE_S * 1000:
            self.errores += 1  # error o fuera de tiempo: el sobreviviente se queda quieto
            return sv["nodo"]
        return nuevo

    def _uso_calles(self):
        """{calle: rutas planificadas que la usan} para elegir la calle que cierra un evento."""
        uso = {}
        for sv in self.mundo.estado.get("sobrevivientes", ()):
            r = sv.get("ruta") or ()
            for a, b in zip(r, r[1:]):
                c = self.grafo.arista.get((a, b))
                if c:
                    uso[c] = uso.get(c, 0) + 1
        return uso

    async def turno(self):
        s, g = self.s, self.grafo
        s["turno"] += 1
        t = s["turno"]
        # 0) los refugios evacuan hacia la zona segura (PRO capacidad)
        for r in s["refugios"].values():
            r["ocupacion"] = max(0, r["ocupacion"] - r["evacua"])
        # 1) eventos de ciudad: la calle desaparece del mapa en vivo
        if any(e[0] == t for e in s["eventos"]):
            ocurridos = events.aplicar(g, s["eventos"], t, s["bloqueadas"], self.rng, self._uso_calles())
            s["log_eventos"] = (s["log_eventos"] + ocurridos)[-10:]
            self._calcular_optimo()
            for ev in ocurridos:
                self.log("evento_ciudad", ronda=s["ronda"], **ev)
        bloq = frozenset(s["bloqueadas"])
        # 2) primero se mueven los zombies (no entran a refugios)
        zm.mover_todos(g, s["zombies"], bloq, {sv["nodo"] for sv in s["sobrevivientes"]}, t, self.rng,
                       g.nodos_refugio)
        zonas = zm.zonas_horda(g, s["zombies"])
        # 3) se publica el mundo: el planner se recalcula UNA vez para todo el turno
        self.mundo.publicar_zombies(t, s["zombies"], s["bloqueadas"], ronda=s["ronda"], corriendo=True,
                                    turnosRestantes=s["turnos_restantes"] - 1, eventos=s["log_eventos"],
                                    refugios=self._pub_refugios())
        # 4) cada sobreviviente consulta POST /paso (en paralelo)
        vivos = s["sobrevivientes"]
        resp = await asyncio.gather(*(self._consultar(sv, t) for sv in vivos))
        mov = {sv["id"]: (sv["nodo"], nuevo if self._valido(sv["nodo"], nuevo, bloq) else sv["nodo"])
               for sv, nuevo in zip(vivos, resp)}
        # 5) mordidas: mismo nodo, zona de horda o cruce por la misma calle
        muertos = bites.mordidos(mov, s["zombies"], zonas)
        st, quedan = s["stats"], []
        for sv in vivos:
            prev, sv["nodo"] = sv["nodo"], mov[sv["id"]][1]
            if sv["id"] in muertos:
                st["mordidos"] += 1
                continue
            if sv["nodo"] in g.nodos_refugio:  # 6) en un refugio: entra si hay cupo
                if self._admitir(g.refugio_de_nodo[sv["nodo"]]):
                    self._salvar(sv, t)
                    continue
                if prev != sv["nodo"]:
                    st["rechazados"] += 1  # llego a un refugio lleno: espera en la puerta
            quedan.append(sv)
        # 7) poblacion continua: siempre N a la vez en la calle
        if self.reponer:
            quedan += self._nuevos(s["poblacion"] - len(quedan))
        s["sobrevivientes"] = quedan
        metricas = self._publicar_turno()
        if t % 10 == 0:
            self.log("turno", ronda=s["ronda"], turno=t, **metricas)
        if self.snapshots and self.snapshots.habilitado and t % self.snapshot_cada == 0:
            try:
                await asyncio.to_thread(self.snapshots.guardar, t, self.exportar())
            except Exception as e:  # un fallo de DynamoDB no debe romper el juego
                print("snapshot fallo:", e)

    def _admitir(self, rid):
        r = self.s["refugios"].get(rid)
        if r is None:
            return True  # sin limite de cupo
        if r["ocupacion"] >= r["capacidad"]:
            return False
        r["ocupacion"] += 1
        return True

    def _salvar(self, sv, t):
        st = self.s["stats"]
        real = t - sv["turno_inicio"]
        st["salvados"] += 1
        st["turnos_salvado"] += real
        if sv.get("optimo"):
            st["ef_suma"] += min(1.0, sv["optimo"] / max(1, real))
            st["ef_n"] += 1

    def _supervivencia(self):
        st = self.s["stats"]
        # continua: salvados / (salvados + mordidos); fija: salvados / todos los que hubo
        total = st["salvados"] + st["mordidos"] if self.reponer else self.s["seq"]
        return round(st["salvados"] / total, 3) if total else None

    def _metricas(self):
        s, st = self.s, self.s["stats"]
        p95 = puntaje.percentil(sorted(self.lat), 0.95)
        return {"salvados": st["salvados"], "mordidos": st["mordidos"], "rechazados": st["rechazados"],
                "supervivencia": self._supervivencia(),
                "eficiencia": round(st["ef_suma"] / st["ef_n"], 3) if st["ef_n"] else None,
                "latenciaP95": round(p95, 2) if p95 is not None else None,
                "pctErrores": round(100 * self.errores / self.consultas, 3) if self.consultas else 0.0,
                "consultas": self.consultas, "turnosRestantes": s["turnos_restantes"] - 1}

    def _publicar_turno(self):
        s, planner, g = self.s, self.mundo.planner, self.grafo
        metricas = self._metricas()
        self.mundo.publicar(
            sobrevivientes=[{"id": sv["id"], "nodo": sv["nodo"],
                             "refugio": g.refugio_de_nodo.get(sv["nodo"]) or planner.refugio_de(sv["id"], sv["nodo"]),
                             "estado": "en_puerta" if sv["nodo"] in g.nodos_refugio else "caminando",
                             "ruta": planner.ruta(sv["nodo"], sv["id"], self.ruta_max)}
                            for sv in s["sobrevivientes"]],
            refugios=self._pub_refugios(), metricas=metricas)
        return metricas

    def exportar(self):
        s = self.s
        return {**s, "zombies": [dict(z) for z in s["zombies"]],
                "sobrevivientes": [dict(sv) for sv in s["sobrevivientes"]]}

    async def _finalizar(self):
        s, st = self.s, self.s["stats"]
        lat = sorted(self.lat)
        pct = lambda p: round(puntaje.percentil(lat, p), 2) if lat else None
        res = {"ronda": s["ronda"], "nombre": RONDAS[s["ronda"]]["nombre"], "turnos": s["turno"],
               "salvados": st["salvados"], "mordidos": st["mordidos"], "rechazados": st["rechazados"],
               "supervivencia": self._supervivencia(),
               "eficiencia": round(st["ef_suma"] / st["ef_n"], 3) if st["ef_n"] else None,
               "turnos_promedio_por_rescate": round(st["turnos_salvado"] / st["salvados"], 2) if st["salvados"] else None,
               "consultas": self.consultas, "errores_o_timeout": self.errores,
               "pct_errores": round(100 * self.errores / self.consultas, 3) if self.consultas else 0,
               "latencia_ms": {"p50": pct(0.5), "p95": pct(0.95), "p99": pct(0.99),
                               "max": round(lat[-1], 2) if lat else None},
               "fin": int(time.time())}
        self.resultados.append(res)
        self.ultimos[s["ronda"]], self.lat_rondas[s["ronda"]] = res, lat
        nota = puntaje.calcular(self.ultimos, self.lat_rondas)
        resumen = [{"ronda": r["ronda"], "nombre": r["nombre"], "turnos": r["turnos"],
                    "salvados": r["salvados"], "mordidos": r["mordidos"], "rechazados": r["rechazados"],
                    "supervivencia": r["supervivencia"], "eficiencia": r["eficiencia"],
                    "latenciaP95": r["latencia_ms"]["p95"], "pctErrores": r["pct_errores"]}
                   for r in (self.ultimos[k] for k in sorted(self.ultimos))]
        self.mundo.publicar(corriendo=False, resultados=resumen, puntaje=nota, metricas=self._metricas())
        self.log("resultado_ronda", **res)
        if nota:
            self.log("puntaje", **nota)
        if self.snapshots and self.snapshots.habilitado:
            try:
                await asyncio.to_thread(self.snapshots.guardar_resultado, s["ronda"], res)
            except Exception as e:
                print("resultado no guardado:", e)

    def puntaje(self):
        return puntaje.calcular(self.ultimos, self.lat_rondas)

    async def _consulta_http(self, sid, nodo, turno):
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(
                base_url=os.environ.get("SIM_URL", "http://127.0.0.1:8000"),
                headers={"x-api-key": os.environ.get("API_KEY", "")},
                timeout=LIMITE_S, limits=httpx.Limits(max_connections=250))
        r = await self._cliente.post("/paso", json={"sobrevivienteId": sid, "nodoActual": nodo, "turno": turno})
        r.raise_for_status()
        return r.json()["siguienteNodo"]
