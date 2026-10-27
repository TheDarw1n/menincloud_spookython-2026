"""Penalizaciones por cercania a zombies: nodos permitidos pero costosos, para que las rutas
dejen margen. Se calculan una vez por turno con el estado publicado y estan en segundos (una
calle de Manta toma ~15-30 s a pie)."""
from collections import defaultdict

P_VECINO = 30.0  # vecino de un zombie visible: puede moverse ahi el proximo turno


def penalizacion(grafo, zombies, prohibidos, bloqueadas):
    """{nodo: segundos extra} para los vecinos de zombies visibles (se suman si hay varios)."""
    pen = defaultdict(float)
    for z in zombies:
        for v, c, _ in grafo.vecinos[z["nodo"]]:
            if c not in bloqueadas:
                pen[v] += P_VECINO
    return {v: p for v, p in pen.items() if v not in prohibidos}
