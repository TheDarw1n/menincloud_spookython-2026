"""Zombies: caminante (1 calle/2 turnos), corredor (2 calles/turno, persigue a <=3 nodos),
horda (casi inmovil; su nodo y vecinos quedan bloqueados), dormido (invisible hasta que un
sobreviviente esta a <=2 nodos; despierta como caminante)."""


def crear(grafo, fracciones, rng, excluir=()):
    libres = [n for n in grafo.nodos if n not in excluir]
    zombies, k = [], 1
    for tipo, f in fracciones.items():
        for _ in range(max(1, round(f * len(grafo.nodos)))):
            nodo = rng.choice(libres)
            zombies.append({"id": f"Z-{k:03d}", "tipo": tipo, "nodo": nodo, "previo": nodo,
                            "visible": tipo != "dormido", "fase": rng.randint(0, 1), "pasos": []})
            k += 1
    return zombies


def _ir(z, v):
    z["pasos"].append([z["nodo"], v])
    z["nodo"] = v


def _paso_aleatorio(grafo, z, bloq, rng):
    opciones = [v for v, c, _ in grafo.vecinos[z["nodo"]] if c not in bloq]
    if opciones:
        _ir(z, rng.choice(opciones))


def _perseguir(grafo, z, bloq, nodos_sobrev):
    if z["nodo"] in nodos_sobrev:
        return True  # ya hay alguien aqui: se queda (mordida)
    cerca = grafo.bfs(z["nodo"], 3, bloq)
    objetivos = [(d, n) for n, (d, _) in cerca.items() if n in nodos_sobrev]
    if not objetivos:
        return False
    _, n = min(objetivos)
    while cerca[n][1] != z["nodo"]:
        n = cerca[n][1]
    _ir(z, n)
    return True


def mover_todos(grafo, zombies, bloq, nodos_sobrev, turno, rng):
    for z in zombies:
        z["previo"], z["pasos"] = z["nodo"], []
        t = z["tipo"]
        if t == "dormido":
            cerca = grafo.bfs(z["nodo"], 2, bloq)
            if any(n in cerca for n in nodos_sobrev):
                z["tipo"], z["visible"] = "caminante", True
        elif t == "caminante":
            if (turno + z["fase"]) % 2 == 0:
                _paso_aleatorio(grafo, z, bloq, rng)
        elif t == "corredor":
            for _ in range(2):
                if not _perseguir(grafo, z, bloq, nodos_sobrev):
                    _paso_aleatorio(grafo, z, bloq, rng)
        elif t == "horda":
            if rng.random() < 0.1:
                _paso_aleatorio(grafo, z, bloq, rng)
