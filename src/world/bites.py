def mordidos(movimientos, zombies, zonas=frozenset()):
    """movimientos: {id: (nodo_previo, nodo_nuevo)}. Mordido si al final del turno comparte
    nodo con un zombie o queda dentro de la zona de una horda (`zonas`: su nodo y vecinos), o
    si se cruza con un zombie por la misma calle en sentido opuesto (cuenta cada uno de los 2
    pasos de un corredor)."""
    nodos = {z["nodo"] for z in zombies} | set(zonas)
    pasos = {(a, b) for z in zombies for a, b in z.get("pasos", [])}
    return {sid for sid, (prev, nuevo) in movimientos.items()
            if nuevo in nodos or (nuevo != prev and (nuevo, prev) in pasos)}
