"""Eventos de ciudad: un puente colapsa o una avenida se bloquea (la arista desaparece en vivo)."""

# El nombre va despues de ":" porque en OSM ya trae su propio tipo ("Avenida 113", "Vía Interbarrial")
TEXTO = {"puente": "Colapsó un puente", "avenida": "Se bloqueó una avenida"}


def _alcanzables(grafo, bloqueadas, origenes):
    vistos, pila = set(origenes), list(origenes)
    while pila:
        u = pila.pop()
        for v, c, _ in grafo.vecinos[u]:
            if c not in bloqueadas and v not in vistos:
                vistos.add(v)
                pila.append(v)
    return len(vistos)


def _sin_partir(grafo, bloqueadas):
    """True si el mapa sigue siendo una sola pieza (ningun refugio ni barrio queda aislado)."""
    return _alcanzables(grafo, bloqueadas, [next(iter(grafo.nodos))]) == len(grafo.nodos)


def _puentes(grafo, bloqueadas):
    """Calles que parten el mapa si se cierran (puentes del grafo sin las calles ya cerradas), con
    Tarjan iterativo en O(V+E). Antes se hacia un DFS completo por cada candidata (~191 avenidas):
    19-32 ms con el bucle de eventos bloqueado justo antes de la rafaga de /paso."""
    disc, low, puentes = {}, {}, set()
    for raiz in grafo.nodos:
        if raiz in disc:
            continue
        disc[raiz] = low[raiz] = len(disc)
        pila = [(raiz, None, iter(grafo.vecinos[raiz]))]
        while pila:
            u, llegada, vecinos = pila[-1]
            for v, c, _ in vecinos:
                if c in bloqueadas or c == llegada:  # por id de calle: dos calles paralelas no son puente
                    continue
                if v in disc:
                    low[u] = min(low[u], disc[v])
                    continue
                disc[v] = low[v] = len(disc)
                pila.append((v, c, iter(grafo.vecinos[v])))
                break
            else:
                pila.pop()
                if pila:
                    padre = pila[-1][0]
                    low[padre] = min(low[padre], low[u])
                    if low[u] > disc[padre]:
                        puentes.add(llegada)
    return puentes


def _todos_llegan(grafo, bloqueadas):
    """True si desde cualquier nodo se sigue llegando a algun refugio."""
    return _alcanzables(grafo, bloqueadas, grafo.nodos_refugio) == len(grafo.nodos)


def aplicar(grafo, eventos, turno, bloqueadas, rng, uso=None):
    """Dispara los eventos programados para `turno` (muta `eventos` y `bloqueadas`) y devuelve
    los ocurridos. Se cierra la calle del tipo pedido que mas rutas planificadas usan (`uso`:
    {calle: n}) para que el impacto se vea en vivo, sin dejar barrios aislados de los refugios."""
    uso = uso or {}
    ocurridos = []
    for ev in [e for e in eventos if e[0] == turno]:
        eventos.remove(ev)
        tipo = ev[1]
        candidatas = [c for c, d in grafo.calles.items() if d["tipo"] == tipo and c not in bloqueadas]
        candidatas = candidatas or [c for c in grafo.calles if c not in bloqueadas]
        # cerrar c deja el mapa en una pieza <=> ya lo esta y c no es un puente
        puentes = _puentes(grafo, set(bloqueadas)) if _sin_partir(grafo, set(bloqueadas)) else None
        candidatas = ([c for c in candidatas if puentes is not None and c not in puentes]
                      or [c for c in candidatas if _todos_llegan(grafo, set(bloqueadas) | {c})]
                      or candidatas)
        if not candidatas:
            continue
        maximo = max(uso.get(c, 0) for c in candidatas)
        elegida = rng.choice(sorted(c for c in candidatas if uso.get(c, 0) == maximo))
        bloqueadas.append(elegida)
        nombre = grafo.calles[elegida].get("nombre")
        base = TEXTO.get(tipo, "Se cerró una calle")
        texto = f"{base}: {nombre} ({elegida})" if nombre else f"{base} ({elegida})"
        ocurridos.append({"turno": turno, "tipo": tipo, "arista": elegida, "texto": texto})
    return ocurridos
