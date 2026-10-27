import threading


class Mundo:
    """Estado publicado del mundo + planner. `estado` es inmutable por convencion:
    cada publicacion crea un dict nuevo (el WebSocket detecta cambios por identidad)."""

    def __init__(self, grafo, planner):
        self.grafo = grafo
        self.planner = planner
        self._lock = threading.Lock()
        self.estado = {
            "turno": 0, "zombies": [], "aristasBloqueadas": [],
            "sobrevivientes": [], "ronda": None, "metricas": {},
            "refugios": [{"id": r, "nodo": n} for r, n in grafo.refugios.items()],
        }

    def prohibidos(self, zombies):
        """Nodos con zombie visible + vecinos de una horda (bloquea nodo y vecinos)."""
        p = set()
        for z in zombies:
            if not z.get("visible", True):
                continue
            p.add(z["nodo"])
            if z["tipo"] == "horda":
                p.update(v for v, _, _ in self.grafo.vecinos[z["nodo"]])
        return frozenset(p)

    PENAL_S = 30.0  # segundos extra por pisar un nodo vecino a un zombie visible

    def penalizados(self, zombies, prohibidos):
        """Nodos adyacentes a un zombie visible: permitidos pero costosos (ruta con margen)."""
        pen = {}
        for z in zombies:
            if z.get("visible", True):
                for v, _, _ in self.grafo.vecinos[z["nodo"]]:
                    if v not in prohibidos:
                        pen[v] = self.PENAL_S
        return pen

    def _recalcular(self, turno, zombies, bloqueadas):
        prohibidos = self.prohibidos(zombies)
        self.planner.actualizar(turno, prohibidos, bloqueadas, self.penalizados(zombies, prohibidos))

    def publicar_zombies(self, turno, zombies, bloqueadas):
        publicos = [{k: z[k] for k in ("id", "tipo", "nodo", "previo", "visible")} for z in zombies]
        with self._lock:
            self.estado = dict(self.estado, turno=turno, zombies=publicos,
                               aristasBloqueadas=sorted(bloqueadas))
            self._recalcular(turno, publicos, bloqueadas)

    def publicar_sobrevivientes(self, sobrevivientes, ronda, metricas):
        with self._lock:
            self.estado = dict(self.estado, sobrevivientes=sobrevivientes,
                               ronda=ronda, metricas=metricas)

    def asegurar_planner(self):
        """Compara contra el turno del SERVIDOR (no el del cliente) con doble verificacion."""
        if self.planner.turno_calculado == self.estado["turno"]:
            return
        with self._lock:
            est = self.estado
            if self.planner.turno_calculado == est["turno"]:
                return
            self._recalcular(est["turno"], est["zombies"], est["aristasBloqueadas"])
