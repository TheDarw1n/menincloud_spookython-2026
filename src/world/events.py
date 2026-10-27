"""Eventos de ciudad: un puente colapsa o una avenida se bloquea (la arista desaparece en vivo)."""

TEXTO = {"puente": "Colapsó el puente", "avenida": "Se bloqueó la avenida"}


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
        candidatas = ([c for c in candidatas if _sin_partir(grafo, set(bloqueadas) | {c})]
                      or [c for c in candidatas if _todos_llegan(grafo, set(bloqueadas) | {c})]
                      or candidatas)
        if not candidatas:
            continue
        maximo = max(uso.get(c, 0) for c in candidatas)
        elegida = rng.choice(sorted(c for c in candidatas if uso.get(c, 0) == maximo))
        bloqueadas.append(elegida)
        nombre = grafo.calles[elegida].get("nombre")
        texto = f"{TEXTO.get(tipo, 'Se cerró la calle')} {nombre or elegida}"
        ocurridos.append({"turno": turno, "tipo": tipo, "arista": elegida, "texto": texto})
    return ocurridos
