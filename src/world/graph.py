import json
from collections import defaultdict

# km/h por tipo de calle (propuesta, ajustable)
VELOCIDAD_KMH = {"avenida": 50, "calle": 30, "callejon": 15, "puente": 40}


class Grafo:
    def __init__(self, data: dict):
        self.nodos = {n["id"]: n for n in data["nodos"]}
        self.refugios = {r["id"]: r["nodo"] for r in data["refugios"]}
        self.info_refugios = {r["id"]: r for r in data["refugios"]}
        self.refugio_de_nodo = {n: r for r, n in self.refugios.items()}
        self.nodos_refugio = frozenset(self.refugio_de_nodo)
        self.barrios = data.get("barrios", [])
        self.calles = {c["id"]: c for c in data["calles"]}
        self.vecinos = defaultdict(list)  # nodo -> [(vecino, id_calle, segundos)]
        self.arista = {}                  # (u, v) -> id_calle (en ambos sentidos)
        for c in data["calles"]:
            kmh = VELOCIDAD_KMH.get(c["tipo"], 30)
            seg = c["distancia_m"] / (kmh / 3.6)
            self.vecinos[c["de"]].append((c["a"], c["id"], seg))
            self.vecinos[c["a"]].append((c["de"], c["id"], seg))
            self.arista.setdefault((c["de"], c["a"]), c["id"])
            self.arista.setdefault((c["a"], c["de"]), c["id"])

    @classmethod
    def desde_archivo(cls, ruta: str):
        with open(ruta, encoding="utf-8") as f:
            return cls(json.load(f))

    def hay_calle(self, u, v, bloqueadas=frozenset()):
        return any(w == v and c not in bloqueadas for w, c, _ in self.vecinos[u])

    def bfs(self, origen, max_depth, bloqueadas=frozenset(), evitar=frozenset()):
        """{nodo: (saltos, padre)} hasta max_depth saltos, sin cruzar calles bloqueadas ni
        entrar a los nodos de `evitar`."""
        res = {origen: (0, None)}
        frontera = [origen]
        for d in range(1, max_depth + 1):
            nueva = []
            for u in frontera:
                for v, c, _ in self.vecinos[u]:
                    if c in bloqueadas or v in res or v in evitar:
                        continue
                    res[v] = (d, u)
                    nueva.append(v)
            frontera = nueva
        return res
