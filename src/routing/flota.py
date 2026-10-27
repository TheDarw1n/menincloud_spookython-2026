"""Flota de rescate (PRO): 5 camionetas, 2 calles por turno, 4 plazas. Son inmunes a las mordidas
pero no pasan por nodos con zombies visibles, zonas de horda ni calles cerradas. Cada turno el
servidor decide a quien recoge cada una y en que orden:
- llena, o con gente y nadie a <= 1 turno de desvio -> entrega en el refugio con cupo mas cercano;
- si no, recoge al sobreviviente de mayor valor =
      (turnos que se ahorra frente a caminar + 2 x riesgo de su nodo) / (1 + turnos en llegarle)
  si se ahorra >= 2 turnos (o esta en riesgo), con asignacion greedy global (cada sobreviviente en
  una sola camioneta) y un 50 % extra por mantener el objetivo del turno anterior.
Solo si la camioneta llega el turno siguiente y su nodo no es riesgoso, el sobreviviente la espera
quieto; si no, sigue caminando y la camioneta lo intercepta. Parametros medidos con A/B (README)."""
import heapq
import math

from .dijkstra import INF

VELOCIDAD = 2     # calles por turno (el doble que a pie)
PLAZAS = 4
ESPERA_MAX = 1    # turnos: si la camioneta llega antes, el sobreviviente la espera quieto
DESVIO_MAX = 1    # con pasajeros solo se desvia por alguien a <= 1 turno (los de arriba esperan)
AHORRO_MIN = 2    # turnos que debe ahorrarle a alguien para ir a buscarlo
CONSTANCIA = 1.5  # premio por mantener el objetivo del turno anterior


def arbol(grafo, origen, bloqueadas, prohibidos):
    """Dijkstra desde una camioneta (tiempo real por tipo de calle): (dist, padre, calles)."""
    dist, padre, calles = {origen: 0.0}, {origen: None}, {origen: 0}
    cola = [(0.0, origen)]
    while cola:
        d, u = heapq.heappop(cola)
        if d > dist[u]:
            continue
        for v, calle, seg in grafo.vecinos[u]:
            if calle in bloqueadas or v in prohibidos:
                continue
            nd = d + seg
            if nd < dist.get(v, INF):
                dist[v], padre[v], calles[v] = nd, u, calles[u] + 1
                heapq.heappush(cola, (nd, v))
    return dist, padre, calles


def camino(padre, destino):
    if destino not in padre:
        return []
    r = []
    while destino is not None:
        r.append(destino)
        destino = padre[destino]
    return r[::-1]


def turnos(calles):
    return math.ceil(calles / VELOCIDAD)


def _calles_a_pie(snap, sid, nodo):
    rid = snap.asignacion.get(sid)
    if rid in snap.saltos and nodo in snap.saltos[rid]:
        return snap.saltos[rid][nodo]
    return min((s[nodo] for s in snap.saltos.values() if nodo in s), default=INF)


def planificar(grafo, snap, sobrevivientes, camionetas, refugios, previos=None):
    """Devuelve ({camioneta: objetivo}, sobrevivientes que esperan). objetivo es
    {"tipo": "recoger", "sid", "nodo"} | {"tipo": "entregar", "refugio", "nodo"} | {"tipo": "libre"}."""
    previos = previos or {}
    libres = {r["id"]: r["capacidad"] - r.get("ocupacion", 0) for r in refugios if r.get("capacidad") is not None}
    arboles = {c["id"]: arbol(grafo, c["nodo"], snap.bloqueadas, snap.prohibidos) for c in camionetas}
    pares = []
    for c in camionetas:
        if c["pasajeros"] >= c.get("capacidad", PLAZAS):
            continue
        calles_c = arboles[c["id"]][2]
        antes = previos.get(c["id"], {}).get("sid")
        for sv in sobrevivientes:
            n = sv["nodo"]
            if n in grafo.nodos_refugio or n not in calles_c:
                continue
            llegar = turnos(calles_c[n])
            if c["pasajeros"] and llegar > DESVIO_MAX:
                continue
            a_pie = _calles_a_pie(snap, sv["id"], n)
            if a_pie == INF:
                continue
            ahorro = a_pie - (llegar + turnos(a_pie))
            riesgo = snap.penal.get(n, 0.0) / 30.0
            if ahorro < AHORRO_MIN and riesgo <= 0:
                continue
            valor = (ahorro + 2 * riesgo) / (1 + llegar) * (CONSTANCIA if sv["id"] == antes else 1.0)
            pares.append((-valor, c["id"], sv["id"], n, llegar))
    pares.sort()
    objetivos, tomados, esperar = {}, set(), set()
    for _, cid, sid, n, llegar in pares:
        if cid in objetivos or sid in tomados:
            continue
        objetivos[cid] = {"tipo": "recoger", "sid": sid, "nodo": n}
        tomados.add(sid)
        if llegar <= ESPERA_MAX and n not in snap.penal and n not in snap.prohibidos:
            esperar.add(sid)
    for c in camionetas:
        if c["id"] in objetivos:
            continue
        if not c["pasajeros"]:
            objetivos[c["id"]] = {"tipo": "libre"}
            continue
        dist = arboles[c["id"]][0]
        alcanzables = sorted((dist[nodo], rid, nodo) for rid, nodo in grafo.refugios.items() if nodo in dist)
        con_cupo = [o for o in alcanzables if libres.get(o[1], INF) >= c["pasajeros"]]
        if not alcanzables:
            objetivos[c["id"]] = {"tipo": "libre"}
            continue
        _, rid, nodo = (con_cupo or alcanzables)[0]
        if rid in libres:
            libres[rid] -= c["pasajeros"]
        objetivos[c["id"]] = {"tipo": "entregar", "refugio": rid, "nodo": nodo}
    return objetivos, frozenset(esperar)
