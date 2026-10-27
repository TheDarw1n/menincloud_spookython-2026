"""Riesgo por zombies (PRO prediccion): en vez de alejar a todos de cualquier zombie (eso alarga
las rutas y, medido, termina mordiendo MAS), se penalizan solo las TRAMPAS: nodos donde un zombie
puede caer el proximo turno y desde los que no quedaria salida. Para eso se anticipa a cada tipo:
- corredor: avanza 2 calles por turno persiguiendo al sobreviviente mas cercano (<= 3 calles); se
  replica su persecucion y se marca todo lo que alcanza a 2 calles;
- caminante: 1 calle cada 2 turnos; si acaba de moverse (previo != nodo) el proximo turno se queda;
- horda: casi inmovil; si avanza, su zona letal (nodo + vecinos) se corre una calle.
Valores en segundos (una calle de Manta toma ~15-30 s a pie)."""
from collections import defaultdict

from ..world.zombies import PROB_HORDA, paso_persecucion

P_TRAMPA = (240.0, 45.0)   # caer ahi con 0 o 1 salidas libres (sin contar por donde entra el zombie)
P_PREDICCION = 25.0        # nodos por los que pasara el corredor que persigue a alguien
P_VECINO = 30.0            # modo sin prediccion: vecino de un zombie visible


def predecir_corredor(grafo, nodo, nodos_sobrev, bloqueadas):
    """Los (hasta) 2 nodos que pisara un corredor el proximo turno si persigue a alguien: misma
    regla que el simulador (sobreviviente mas cercano a <= 3 calles, sin entrar a refugios)."""
    camino = []
    for _ in range(2):
        sig = paso_persecucion(grafo, nodo, nodos_sobrev, bloqueadas, grafo.nodos_refugio)
        if sig is None or sig == nodo:
            break
        camino.append(sig)
        nodo = sig
    return camino


def llegadas(grafo, zombies, bloqueadas):
    """{nodo: {nodos desde los que un zombie puede entrar ahi el proximo turno}}."""
    entra = defaultdict(set)
    for z in zombies:
        n, tipo = z["nodo"], z["tipo"]
        if tipo == "corredor":
            for v, (d, padre) in grafo.bfs(n, 2, bloqueadas, evitar=grafo.nodos_refugio).items():
                if d:
                    entra[v].add(padre)
        elif tipo == "caminante" and z.get("previo", n) == n:  # le toca moverse
            for v, c, _ in grafo.vecinos[n]:
                if c not in bloqueadas and v not in grafo.nodos_refugio:
                    entra[v].add(n)
    return entra


def penalizacion(grafo, zombies, prohibidos, bloqueadas, sobrevivientes=(), prediccion=True):
    """{nodo: segundos extra}. Con prediccion: trampas + camino previsto de los corredores.
    Sin prediccion: solo los vecinos de cada zombie visible."""
    pen = defaultdict(float)
    if not prediccion:
        for z in zombies:
            for v, c, _ in grafo.vecinos[z["nodo"]]:
                if c not in bloqueadas:
                    pen[v] += P_VECINO
        return {v: p for v, p in pen.items() if v not in prohibidos}
    # zonas que una horda podria cubrir si avanza (10 % por turno): cuentan como salida dudosa
    dudosos = set()
    for z in zombies:
        if z["tipo"] == "horda" and PROB_HORDA > 0:
            dudosos.update(v for v, (d, _) in grafo.bfs(z["nodo"], 2, bloqueadas).items() if d == 2)
    for v, desde in llegadas(grafo, zombies, bloqueadas).items():
        if v in prohibidos:
            continue
        salidas = sum(1 for w, c, _ in grafo.vecinos[v]
                      if c not in bloqueadas and w not in prohibidos and w not in desde and w not in dudosos)
        if salidas < len(P_TRAMPA):
            pen[v] += P_TRAMPA[salidas]
    nodos_sobrev = {s["nodo"] for s in sobrevivientes}
    for z in zombies:
        if z["tipo"] == "corredor":
            for v in predecir_corredor(grafo, z["nodo"], nodos_sobrev, bloqueadas):
                pen[v] += P_PREDICCION
    return {v: p for v, p in pen.items() if v not in prohibidos}
