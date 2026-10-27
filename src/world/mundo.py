import json
import threading

from .zombies import zonas_horda


class Mundo:
    """Estado publicado del mundo + planner. `estado` es inmutable por convencion: cada
    publicacion crea un dict nuevo (el WebSocket detecta cambios por identidad). El planner se
    recalcula UNA vez por turno a partir de este mismo estado publicado."""

    def __init__(self, grafo, planner):
        self.grafo = grafo
        self.planner = planner
        self._lock = threading.Lock()
        self._json = (None, "")  # (estado, texto): serializado una sola vez por publicacion
        self.estado = {
            "turno": 0, "ronda": None, "corriendo": False, "turnosRestantes": 0,
            "zombies": [], "aristasBloqueadas": [], "zonasHorda": [], "sobrevivientes": [],
            "refugios": [{"id": r, "nodo": n, "nombre": grafo.info_refugios[r].get("nombre", r)}
                         for r, n in grafo.refugios.items()],
            "metricas": {},
        }

    def publicar_zombies(self, turno, zombies, bloqueadas, **extra):
        """Inicio de turno: zombies ya movidos. Publica y recalcula el planner (una vez)."""
        publicos = [{"id": z["id"], "tipo": z["tipo"], "nodo": z["nodo"], "previo": z["previo"],
                     "visible": z["visible"], "pasos": [list(p) for p in z.get("pasos", ())]}
                    for z in zombies]
        with self._lock:
            self.estado = dict(self.estado, turno=turno, zombies=publicos,
                               aristasBloqueadas=sorted(bloqueadas),
                               zonasHorda=sorted(zonas_horda(self.grafo, publicos)), **extra)
            self.planner.actualizar(self.estado)

    def publicar(self, **campos):
        with self._lock:
            self.estado = dict(self.estado, **campos)

    def json_estado(self):
        """El estado en JSON, serializado UNA vez por publicacion: lo comparten /estado y todos
        los WebSocket (con muchos visores, serializar 40 KB por cliente costaba mas que /paso)."""
        est, (previo, texto) = self.estado, self._json
        if previo is not est:
            texto = json.dumps(est, ensure_ascii=False, separators=(",", ":"))
            self._json = (est, texto)
        return texto

    def asegurar_planner(self):
        """Compara contra el turno del SERVIDOR (no el del cliente) con doble verificacion."""
        if self.planner.turno_calculado == self.estado["turno"]:
            return
        with self._lock:
            est = self.estado
            if self.planner.turno_calculado == est["turno"]:
                return
            self.planner.actualizar(est)
