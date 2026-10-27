from dataclasses import dataclass

from .dijkstra import dijkstra_inverso


@dataclass(frozen=True)
class Snapshot:
    turno: int
    tablas: dict          # id_refugio -> {nodo: segundos hasta ese refugio}
    prohibidos: frozenset
    bloqueadas: frozenset
    penal: dict = None


class Planner:
    """1 Dijkstra inverso por refugio, recalculado SOLO cuando cambia el mundo
    (una vez por turno). Los snapshots son inmutables y se reemplazan de forma atomica,
    asi que /paso puede leerlos desde muchos hilos sin lock."""

    def __init__(self, grafo):
        self.grafo = grafo
        self._snap = Snapshot(-1, {}, frozenset(), frozenset())

    @property
    def turno_calculado(self):
        return self._snap.turno

    def actualizar(self, turno, prohibidos, bloqueadas, penal=None):
        prohibidos, bloqueadas = frozenset(prohibidos), frozenset(bloqueadas)
        tablas = {
            rid: dijkstra_inverso(self.grafo, nodo, bloqueadas, prohibidos, penal)
            for rid, nodo in self.grafo.refugios.items()
        }
        self._snap = Snapshot(turno, tablas, prohibidos, bloqueadas, penal or {})

    def _siguiente(self, snap, nodo):
        if nodo in self.grafo.refugios.values():
            return nodo
        mejor, mejor_costo = nodo, float("inf")
        for tabla in snap.tablas.values():
            for v, calle, _ in self.grafo.vecinos[nodo]:
                if calle in snap.bloqueadas or v in snap.prohibidos:
                    continue
                c = tabla.get(v, float("inf"))
                if c < mejor_costo:
                    mejor, mejor_costo = v, c
        return mejor  # si no hay salida segura, se queda quieto

    def siguiente_nodo(self, nodo):
        return self._siguiente(self._snap, nodo)

    def ruta(self, nodo, max_nodos=25):
        """Ruta planificada (para el mapa): sigue siguiente_nodo hasta el refugio."""
        snap = self._snap
        ruta, visto, actual = [nodo], {nodo}, nodo
        for _ in range(max_nodos):
            sig = self._siguiente(snap, actual)
            if sig == actual or sig in visto:
                break
            ruta.append(sig)
            visto.add(sig)
            actual = sig
        return ruta
