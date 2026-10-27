"""Eventos de ciudad: un puente colapsa o una avenida se bloquea (la arista desaparece en vivo)."""


def aplicar(grafo, eventos, turno, bloqueadas, rng):
    """Dispara los eventos programados para `turno`. Muta `eventos` y `bloqueadas`."""
    for ev in [e for e in eventos if e[0] == turno]:
        eventos.remove(ev)
        candidatas = [c for c, d in grafo.calles.items() if d["tipo"] == ev[1] and c not in bloqueadas]
        candidatas = candidatas or [c for c in grafo.calles if c not in bloqueadas]
        if candidatas:
            bloqueadas.append(rng.choice(candidatas))
