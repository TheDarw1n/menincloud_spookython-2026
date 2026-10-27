import heapq


def dijkstra_inverso(grafo, destino, bloqueadas=frozenset(), prohibidos=frozenset(), penal=None):
    """Costo (segundos) desde cada nodo hasta `destino`. Calles bidireccionales.
    `penal`: {nodo: segundos extra} por pisar ese nodo (cercania a zombies)."""
    penal = penal or {}
    dist = {destino: 0.0}
    cola = [(0.0, destino)]
    while cola:
        d, u = heapq.heappop(cola)
        if d > dist.get(u, float("inf")):
            continue
        extra = penal.get(u, 0.0)  # costo de entrar a u viniendo desde v
        for v, calle, seg in grafo.vecinos[u]:
            if calle in bloqueadas or v in prohibidos:
                continue
            nd = d + seg + extra
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(cola, (nd, v))
    return dist
