"""Capacidad de refugios (PRO): repartir a los sobrevivientes para que ninguno llegue a un
refugio lleno. Cada refugio tiene cupo (personas adentro a la vez) y evacua E personas al inicio
de cada turno hacia la zona segura, asi que para alguien que llega en t turnos (el que llega este
mismo turno ya no ve otra evacuacion) el cupo proyectado es
    capacidad - ocupacion + E * (t - 1) - (asignados que llegan antes).
Cada turno se asigna en orden de llegada (el mas cercano primero) al refugio mas barato que
tenga cupo proyectado. Se recalcula desde cero: medido, "fijar" el refugio previo (aunque sea con
un 15 % de preferencia) hacia que los zombies acorralaran a mas gente (R3: 178 -> 309 mordidas)."""
import bisect

from .dijkstra import INF


def asignar(tablas, saltos, sobrevivientes, refugios):
    """tablas/saltos: {refugio: {nodo: segundos | calles}}; refugios: estado publicado con
    capacidad, ocupacion y evacuaPorTurno. Devuelve ({sobreviviente: refugio}, llenos ahora)."""
    cupos = {r["id"]: r for r in refugios if r.get("capacidad") is not None}
    llenos = frozenset(rid for rid, r in cupos.items() if r.get("ocupacion", 0) >= r["capacidad"])
    if not cupos:
        return {}, llenos
    pedidos = []
    for sv in sobrevivientes:
        n, opciones = sv["nodo"], []
        for rid, tabla in tablas.items():
            c = tabla.get(n, INF)
            if c < INF:
                opciones.append((c, saltos[rid][n], rid))
        if opciones:
            opciones.sort()
            pedidos.append((min(eta for _, eta, _ in opciones), sv["id"], opciones))
    pedidos.sort()
    llegadas = {rid: [] for rid in tablas}  # ETAs (en turnos) ya comprometidos por refugio
    asignacion = {}
    for _, sid, opciones in pedidos:
        elegido = opciones[0]  # si ninguno tiene cupo proyectado: el mas barato (espera en la puerta)
        for op in opciones:
            _, eta, rid = op
            r = cupos.get(rid)
            cupo = INF if r is None else (r["capacidad"] - r.get("ocupacion", 0)
                                          + r.get("evacuaPorTurno", 0) * max(0, eta - 1))
            if bisect.bisect_right(llegadas[rid], eta) < cupo:
                elegido = op
                break
        _, eta, rid = elegido
        bisect.insort(llegadas[rid], eta)
        asignacion[sid] = rid
    return asignacion, llenos
