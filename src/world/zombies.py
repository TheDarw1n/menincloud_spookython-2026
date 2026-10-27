"""Zombies: caminante (1 calle/2 turnos), corredor (2 calles/turno, persigue a <=3 nodos),
horda (casi inmovil; su nodo y TODOS sus vecinos son letales), dormido (invisible hasta que un
sobreviviente esta a <=2 nodos; despierta como caminante). Ningun zombie entra a un refugio
(son puntos fortificados)."""

RADIO_CORREDOR = 3
RADIO_DORMIDO = 2
PROB_HORDA = 0.1  # probabilidad de que una horda avance una calle en un turno


def crear(grafo, fracciones, rng, excluir=()):
    excluir = set(excluir)
    junto_refugio = {v for r in grafo.nodos_refugio for v, _, _ in grafo.vecinos[r]}
    zombies, k = [], 1
    for tipo, f in fracciones.items():
        # una horda pegada a un refugio le bloquearia la entrada: nace a 2+ calles
        libres = [n for n in grafo.nodos if n not in excluir and not (tipo == "horda" and n in junto_refugio)]
        for _ in range(max(1, round(f * len(grafo.nodos)))):
            nodo = rng.choice(libres)
            zombies.append({"id": f"Z-{k:03d}", "tipo": tipo, "nodo": nodo, "previo": nodo,
                            "visible": tipo != "dormido", "fase": rng.randint(0, 1), "pasos": []})
            k += 1
    return zombies


def zonas_horda(grafo, zombies):
    """Nodos letales de las hordas: su nodo y todos sus vecinos (menos los refugios)."""
    zona = set()
    for z in zombies:
        if z["tipo"] == "horda":
            zona.add(z["nodo"])
            zona.update(v for v, _, _ in grafo.vecinos[z["nodo"]])
    return zona - grafo.nodos_refugio


def _ir(z, v):
    z["pasos"].append([z["nodo"], v])
    z["nodo"] = v


def _paso_aleatorio(grafo, z, bloq, rng, vetados):
    opciones = [v for v, c, _ in grafo.vecinos[z["nodo"]] if c not in bloq and v not in vetados]
    if opciones:
        _ir(z, rng.choice(opciones))


def paso_persecucion(grafo, nodo, nodos_sobrev, bloq, vetados=frozenset()):
    """Siguiente nodo de un corredor que persigue al sobreviviente mas cercano (<= 3 calles,
    desempate por id de nodo). None si no hay nadie cerca; el mismo nodo si ya esta sobre
    alguien. El planner la reutiliza para predecir a los corredores (PRO)."""
    if nodo in nodos_sobrev:
        return nodo
    cerca = grafo.bfs(nodo, RADIO_CORREDOR, bloq, evitar=vetados)
    objetivos = [(d, n) for n, (d, _) in cerca.items() if n in nodos_sobrev]
    if not objetivos:
        return None
    _, n = min(objetivos)
    while cerca[n][1] != nodo:
        n = cerca[n][1]
    return n


def mover_todos(grafo, zombies, bloq, nodos_sobrev, turno, rng, vetados=frozenset()):
    """Mueve a todos los zombies un turno. `vetados`: nodos a los que no entran (refugios)."""
    for z in zombies:
        z["previo"], z["pasos"] = z["nodo"], []
        t = z["tipo"]
        if t == "dormido":
            cerca = grafo.bfs(z["nodo"], RADIO_DORMIDO, bloq)
            if not cerca.keys().isdisjoint(nodos_sobrev):
                z["tipo"], z["visible"] = "caminante", True
        elif t == "caminante":
            if (turno + z["fase"]) % 2 == 0:
                _paso_aleatorio(grafo, z, bloq, rng, vetados)
        elif t == "corredor":
            for _ in range(2):
                sig = paso_persecucion(grafo, z["nodo"], nodos_sobrev, bloq, vetados)
                if sig is None:
                    _paso_aleatorio(grafo, z, bloq, rng, vetados)
                elif sig == z["nodo"]:
                    break  # ya esta sobre un sobreviviente: se queda
                else:
                    _ir(z, sig)
        elif t == "horda":
            if rng.random() < PROB_HORDA:
                _paso_aleatorio(grafo, z, bloq, rng, vetados)
