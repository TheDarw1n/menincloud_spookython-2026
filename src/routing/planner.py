from dataclasses import dataclass, field

from ..world.zombies import zonas_horda
from . import riesgo
from .dijkstra import INF, dijkstra_inverso

ESPERA_S = 20.0  # costo de quedarse quieto un turno (~ lo que toma una calle a pie)


@dataclass(frozen=True)
class Snapshot:
    turno: int
    tablas: dict = field(default_factory=dict)   # id_refugio -> {nodo: segundos hasta ese refugio}
    saltos: dict = field(default_factory=dict)   # id_refugio -> {nodo: calles (turnos) hasta ese refugio}
    prohibidos: frozenset = frozenset()          # nodos letales: zombie visible o zona de horda
    bloqueadas: frozenset = frozenset()          # calles cerradas por eventos
    cruces: frozenset = frozenset()              # pasos (u, v) que se cruzan con un zombie en la misma calle
    penal: dict = field(default_factory=dict)    # nodo -> segundos extra (cercania a zombies)


class Planner:
    """1 Dijkstra inverso por refugio, recalculado SOLO cuando cambia el mundo (una vez por
    turno) a partir del estado publicado. Los snapshots son inmutables y se reemplazan de forma
    atomica, asi que /paso los lee desde muchos hilos sin lock: cada consulta es O(grado)."""

    def __init__(self, grafo, prediccion=True):
        self.grafo = grafo
        self.prediccion = prediccion  # PRO: anticipar a corredores, caminantes y hordas
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
            # no se planifica a traves de OTRO refugio: pisarlo ya es llegar a ese refugio
            evitar = prohibidos | (g.nodos_refugio - {nodo})
            tablas[rid], saltos[rid] = dijkstra_inverso(g, nodo, bloqueadas, evitar, penal)
        self._snap = Snapshot(est.get("turno", 0), tablas, saltos, prohibidos, bloqueadas, cruces, penal)

    # ---------- consultas (ruta caliente de /paso) ----------
    def _tablas(self, snap, sid):
        return list(snap.tablas.values())

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
        if nodo not in self.grafo.nodos or nodo in self.grafo.nodos_refugio:
            return nodo  # nodo desconocido o ya en un refugio: se queda
        mejor, costo = self._mejor(snap, nodo, self._tablas(snap, sid))
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

    def ruta(self, nodo, sid=None, max_nodos=25):
        """Ruta planificada (para el mapa): baja por la tabla hasta el refugio."""
        snap, g = self._snap, self.grafo
        tablas = self._tablas(snap, sid)
        ruta, actual = [nodo], nodo
        for _ in range(max_nodos):
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
