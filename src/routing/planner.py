from dataclasses import dataclass, field, replace

from ..world.zombies import zonas_horda
from . import capacidad, flota, riesgo
from .dijkstra import INF, dijkstra_inverso

ESPERA_S = 60.0  # costo de quedarse quieto un turno (~ una calle tipica con su interseccion)


@dataclass(frozen=True)
class Snapshot:
    turno: int
    tablas: dict = field(default_factory=dict)   # id_refugio -> {nodo: segundos hasta ese refugio}
    saltos: dict = field(default_factory=dict)   # id_refugio -> {nodo: calles (turnos) hasta ese refugio}
    prohibidos: frozenset = frozenset()          # nodos letales: zombie visible o zona de horda
    bloqueadas: frozenset = frozenset()          # calles cerradas por eventos
    cruces: frozenset = frozenset()              # pasos (u, v) que se cruzan con un zombie en la misma calle
    penal: dict = field(default_factory=dict)    # nodo -> segundos extra (trampas y prediccion)
    asignacion: dict = field(default_factory=dict)  # sobreviviente -> refugio (PRO capacidad)
    llenos: frozenset = frozenset()                 # refugios sin cupo en este turno
    flota: dict = field(default_factory=dict)       # camioneta -> objetivo del turno (PRO flota)
    esperar: frozenset = frozenset()                # sobrevivientes que esperan a su camioneta
    nodos: dict = field(default_factory=dict)       # sobreviviente propio -> su nodo en este turno


class Planner:
    """1 Dijkstra inverso por refugio, recalculado SOLO cuando cambia el mundo (una vez por
    turno) a partir del estado publicado. Los snapshots son inmutables y se reemplazan de forma
    atomica, asi que /paso los lee desde muchos hilos sin lock: cada consulta es O(grado)."""

    def __init__(self, grafo, prediccion=True, capacidad=True, flota=True):
        self.grafo = grafo
        self.prediccion = prediccion  # PRO: anticipar a corredores, caminantes y hordas
        self.usa_capacidad = capacidad  # PRO: repartir segun el cupo de los refugios
        self.usa_flota = flota          # PRO: decidir a quien recoge cada camioneta
        self._snap = Snapshot(-1)

    @property
    def turno_calculado(self):
        return self._snap.turno

    def actualizar(self, est):
        g = self.grafo
        bloqueadas = frozenset(est.get("aristasBloqueadas", ()))
        visibles = [z for z in est.get("zombies", ()) if z.get("visible", True)]
        prohibidos = frozenset(z["nodo"] for z in visibles) | frozenset(zonas_horda(g, visibles))
        # un zombie que recorrio a->b este turno muerde a quien vaya de b a a por esa calle
        cruces = frozenset((b, a) for z in visibles for a, b in z.get("pasos", ()))
        penal = riesgo.penalizacion(g, visibles, prohibidos, bloqueadas,
                                    est.get("sobrevivientes", ()), self.prediccion)
        tablas, saltos = {}, {}
        for rid, nodo in g.refugios.items():
            if nodo in prohibidos:  # un zombie ocupa el refugio (solo si no son fortificados)
                tablas[rid], saltos[rid] = {}, {}
                continue
            # no se planifica a traves de OTRO refugio: pisarlo ya es llegar a ese refugio
            evitar = prohibidos | (g.nodos_refugio - {nodo})
            tablas[rid], saltos[rid] = dijkstra_inverso(g, nodo, bloqueadas, evitar, penal)
        asignacion, llenos = {}, frozenset()
        if self.usa_capacidad:
            asignacion, llenos = capacidad.asignar(tablas, saltos, est.get("sobrevivientes", ()),
                                                   est.get("refugios", ()))
        nodos = {sv["id"]: sv["nodo"] for sv in est.get("sobrevivientes", ())}
        snap = Snapshot(est.get("turno", 0), tablas, saltos, prohibidos, bloqueadas, cruces, penal,
                        asignacion, llenos, nodos=nodos)
        if self.usa_flota and est.get("camionetas"):
            objetivos, esperar = flota.planificar(g, snap, est.get("sobrevivientes", ()), est["camionetas"],
                                                  est.get("refugios", ()), self._snap.flota)
            snap = replace(snap, flota=objetivos, esperar=esperar)
        self._snap = snap

    # ---------- consultas (ruta caliente de /paso) ----------
    @staticmethod
    def _propio(snap, sid, nodo):
        """La asignacion por cupo y la espera de camioneta son de los sobrevivientes del simulador.
        Un id externo que coincida con uno propio ("S-0001" es tambien el formato del contrato) pero
        en otro nodo se rutea como cualquier id externo."""
        return sid is not None and snap.nodos.get(sid) == nodo

    def _tablas(self, snap, sid, nodo):
        rid = snap.asignacion.get(sid) if self._propio(snap, sid, nodo) else None
        return [snap.tablas[rid]] if rid in snap.tablas else list(snap.tablas.values())

    def refugio_de(self, sid, nodo):
        """Refugio al que va (asignado por capacidad o el mas barato desde su nodo)."""
        snap = self._snap
        rid = snap.asignacion.get(sid) if self._propio(snap, sid, nodo) else None
        if rid is None and snap.tablas:
            rid = min(snap.tablas, key=lambda r: snap.tablas[r].get(nodo, INF))
        return rid

    def _movimientos(self, snap, nodo):
        """Vecinos a los que se puede ir sin morir este turno, con los segundos de la calle."""
        for v, calle, seg in self.grafo.vecinos[nodo]:
            if calle in snap.bloqueadas or v in snap.prohibidos or (nodo, v) in snap.cruces:
                continue
            yield v, seg

    def _mejor(self, snap, nodo, tablas):
        """Paso de menor costo real: calle(u,v) + penal[v] + resto del camino desde v."""
        mejor, costo = nodo, INF
        for v, seg in self._movimientos(snap, nodo):
            base = seg + snap.penal.get(v, 0.0)
            for t in tablas:
                c = base + t.get(v, INF)
                if c < costo:
                    mejor, costo = v, c
        if nodo not in snap.prohibidos:  # quedarse quieto tambien es una jugada valida
            quieto = ESPERA_S + snap.penal.get(nodo, 0.0)
            for t in tablas:
                c = quieto + t.get(nodo, INF)
                if c < costo:
                    mejor, costo = nodo, c
        return mejor, costo

    def _siguiente(self, snap, nodo, sid=None):
        if nodo not in self.grafo.nodos or (nodo in self.grafo.nodos_refugio and nodo not in snap.prohibidos):
            return nodo  # nodo desconocido o en la puerta de un refugio seguro: se queda
        if sid in snap.esperar and nodo not in snap.prohibidos and self._propio(snap, sid, nodo):
            return nodo  # su camioneta llega en <= 3 turnos
        mejor, costo = self._mejor(snap, nodo, self._tablas(snap, sid, nodo))
        if costo == INF:
            mejor, costo = self._mejor(snap, nodo, list(snap.tablas.values()))
        if costo == INF and nodo in snap.prohibidos:
            # sin camino seguro a ningun refugio y su nodo es letal: huye a cualquier vecino seguro
            seguros = [v for v, _ in self._movimientos(snap, nodo)]
            if seguros:
                return min(seguros, key=lambda v: (snap.penal.get(v, 0.0), v))
        return mejor

    def siguiente_nodo(self, nodo, sid=None):
        return self._siguiente(self._snap, nodo, sid)

    # ---------- flota (PRO) ----------
    def objetivos_flota(self):
        return self._snap.flota

    def esperando(self, sid):
        return sid in self._snap.esperar

    def camino_camioneta(self, origen, destino):
        """Camino completo de una camioneta (evita zombies visibles, hordas y calles cerradas)."""
        snap = self._snap
        _, padre, _ = flota.arbol(self.grafo, origen, snap.bloqueadas, snap.prohibidos)
        return flota.camino(padre, destino)

    def pasos_camioneta(self, origen, destino):
        """Las (hasta) 2 calles que avanza este turno."""
        return self.camino_camioneta(origen, destino)[1:1 + flota.VELOCIDAD]

    def ruta(self, nodo, sid=None, max_nodos=25):
        """Ruta planificada (para el mapa): el primer paso es exactamente el que responde /paso
        (respeta cruces y esperas); desde ahi baja por la tabla hasta el refugio."""
        snap, g = self._snap, self.grafo
        tablas = self._tablas(snap, sid, nodo)
        ruta, actual = [nodo], nodo
        primero = self._siguiente(snap, nodo, sid)
        if primero != nodo:
            ruta.append(primero)
            actual = primero
        for _ in range(max_nodos - 1):
            if actual in g.nodos_refugio or actual not in g.nodos:
                break
            sig, costo = None, INF
            for v, calle, seg in g.vecinos[actual]:
                if calle in snap.bloqueadas or v in snap.prohibidos or v in ruta:
                    continue
                base = seg + snap.penal.get(v, 0.0)
                for t in tablas:
                    c = base + t.get(v, INF)
                    if c < costo:
                        sig, costo = v, c
            if sig is None:
                break
            ruta.append(sig)
            actual = sig
        return ruta
