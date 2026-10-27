import heapq

INF = float("inf")


def dijkstra_inverso(grafo, destino, bloqueadas=frozenset(), prohibidos=frozenset(), penal=None):
    """Costo (segundos) y calles desde cada nodo hasta `destino`. Calles bidireccionales.
    `penal`: {nodo: segundos extra} por pisar ese nodo (cercania a zombies). dist[v] incluye las
    penalizaciones de los nodos que vienen DESPUES de v, no la de v: quien decide el paso u->v
    suma calle(u,v) + penal[v] + dist[v].
    Devuelve (dist, saltos); saltos = calles del camino elegido = turnos que tarda a pie."""
    penal = penal or {}
    dist, saltos = {destino: 0.0}, {destino: 0}
    cola = [(0.0, destino)]
    while cola:
        d, u = heapq.heappop(cola)
        if d > dist[u]:
            continue
        extra = penal.get(u, 0.0)  # costo de entrar a u viniendo desde v
        for v, calle, seg in grafo.vecinos[u]:
            if calle in bloqueadas or v in prohibidos:
                continue
            nd = d + seg + extra
            if nd < dist.get(v, INF):
                dist[v], saltos[v] = nd, saltos[u] + 1
                heapq.heappush(cola, (nd, v))
    return dist, saltos
