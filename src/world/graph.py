import json
from collections import defaultdict

# km/h por tipo de calle (propuesta, ajustable)
VELOCIDAD_KMH = {"avenida": 50, "calle": 30, "callejon": 15, "puente": 40}


class Grafo:
    def __init__(self, data: dict):
        self.nodos = {n["id"]: n for n in data["nodos"]}
        self.refugios = {r["id"]: r["nodo"] for r in data["refugios"]}
        self.calles = {c["id"]: c for c in data["calles"]}
        self.vecinos = defaultdict(list)  # nodo -> [(vecino, id_calle, segundos)]
        for c in data["calles"]:
            kmh = VELOCIDAD_KMH.get(c["tipo"], 30)
            seg = c["distancia_m"] / (kmh / 3.6)
            self.vecinos[c["de"]].append((c["a"], c["id"], seg))
            self.vecinos[c["a"]].append((c["de"], c["id"], seg))

    @classmethod
    def desde_archivo(cls, ruta: str):
        with open(ruta, encoding="utf-8") as f:
            return cls(json.load(f))

    def hay_calle(self, u, v, bloqueadas=frozenset()):
        return any(w == v and c not in bloqueadas for w, c, _ in self.vecinos[u])

    def bfs(self, origen, max_depth, bloqueadas=frozenset()):
        """{nodo: (saltos, padre)} hasta max_depth saltos, sin cruzar calles bloqueadas."""
        res = {origen: (0, None)}
        frontera = [origen]
        for d in range(1, max_depth + 1):
            nueva = []
            for u in frontera:
                for v, c, _ in self.vecinos[u]:
                    if c in bloqueadas or v in res:
                        continue
                    res[v] = (d, u)
                    nueva.append(v)
            frontera = nueva
        return res
