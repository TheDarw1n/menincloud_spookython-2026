def mordidos(movimientos, zombies):
    """movimientos: {id: (nodo_previo, nodo_nuevo)}. Mordido si al final del turno comparte
    nodo con un zombie, o si se cruzan por la misma calle en sentidos opuestos."""
    nodos = {z["nodo"] for z in zombies}
    pasos = {(a, b) for z in zombies for a, b in z.get("pasos", [])}
    return {sid for sid, (prev, nuevo) in movimientos.items()
            if nuevo in nodos or (nuevo != prev and (nuevo, prev) in pasos)}
