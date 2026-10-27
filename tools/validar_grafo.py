"""Valida un grafo antes de usarlo. Uso: python tools/validar_grafo.py data/manta_graph.json
Ademas de la estructura y la conexidad revisa lo que necesita el juego: 4 refugios en nodos
distintos, >= 2 puentes (ronda 2), >= 15 avenidas (ronda 3), < 8 % de callejones sin salida,
>= 25 nodos en cada barrio de la historia y ninguna calle duplicada ni lazo."""
import collections
import json
import sys

TIPOS = ("avenida", "calle", "callejon", "puente")
BARRIOS_HISTORIA = ("Tarqui", "Los Esteros", "Barbasquillo", "Jocay")
MIN_PUENTES, MIN_AVENIDAS, MAX_SIN_SALIDA, MIN_NODOS_BARRIO = 2, 15, 0.08, 25


def validar(g):
    """Devuelve (errores, avisos, resumen) del grafo g (dict ya cargado del JSON)."""
    errores, avisos = [], []
    nodos, calles, refugios = g.get("nodos", []), g.get("calles", []), g.get("refugios", [])
    ids = {n["id"] for n in nodos}
    if not nodos:
        return ["el grafo no tiene nodos"], avisos, ""
    if len(ids) != len(nodos):
        errores.append("hay ids de nodo repetidos")
    if len({c["id"] for c in calles}) != len(calles):
        errores.append("hay ids de calle repetidos")

    adj, pares = collections.defaultdict(set), set()
    for c in calles:
        if c["de"] not in ids or c["a"] not in ids:
            errores.append(f"calle {c['id']} apunta a nodo inexistente")
        if c["tipo"] not in TIPOS:
            errores.append(f"calle {c['id']} con tipo invalido: {c['tipo']}")
        if not isinstance(c["distancia_m"], int) or c["distancia_m"] <= 0:
            errores.append(f"calle {c['id']} con distancia_m que no es entero > 0: {c['distancia_m']}")
        if c["de"] == c["a"]:
            errores.append(f"calle {c['id']} es un lazo ({c['de']} -> {c['a']})")
        par = frozenset((c["de"], c["a"]))
        if par in pares:
            errores.append(f"calle {c['id']} duplica otra calle entre {c['de']} y {c['a']}")
        pares.add(par)
        adj[c["de"]].add(c["a"])
        adj[c["a"]].add(c["de"])

    if len(refugios) != 4:
        errores.append(f"se esperaban 4 refugios, hay {len(refugios)}")
    for r in refugios:
        if r["nodo"] not in ids:
            errores.append(f"refugio {r['id']} en nodo inexistente")
    if len({r["nodo"] for r in refugios}) != len(refugios):
        errores.append("hay refugios en el mismo nodo")

    vistos, pila = set(), [nodos[0]["id"]]
    while pila:
        n = pila.pop()
        if n not in vistos:
            vistos.add(n)
            pila.extend(adj[n] - vistos)
    if vistos != ids:
        errores.append(f"grafo no conexo: {len(ids) - len(vistos)} nodos inalcanzables")

    tipos = collections.Counter(c["tipo"] for c in calles)
    if tipos["puente"] < MIN_PUENTES:
        errores.append(f"hay {tipos['puente']} puentes; la ronda 2 necesita >= {MIN_PUENTES}")
    if tipos["avenida"] < MIN_AVENIDAS:
        errores.append(f"hay {tipos['avenida']} avenidas; la ronda 3 necesita >= {MIN_AVENIDAS}")
    sin_salida = sum(1 for i in ids if len(adj[i]) == 1)
    if sin_salida >= MAX_SIN_SALIDA * len(ids):
        errores.append(f"{sin_salida} callejones sin salida ({100 * sin_salida / len(ids):.1f} %), "
                       f"el maximo es {100 * MAX_SIN_SALIDA:.0f} %")

    barrios = {b["id"]: b["nombre"] for b in g.get("barrios", [])}
    por_barrio = collections.Counter(n.get("barrio") for n in nodos)
    raros = [n for n in nodos if n.get("barrio") not in barrios and n.get("barrio") != "otro"]
    if raros:
        errores.append(f"{len(raros)} nodos con barrio desconocido (ej. {raros[0]['id']}: "
                       f"{raros[0].get('barrio')}); debe ser un id de la lista barrios u 'otro'")
    for nombre in BARRIOS_HISTORIA:
        bid = next((i for i, nb in barrios.items() if nb == nombre), None)
        if bid is None:
            errores.append(f"falta el barrio {nombre} en la lista barrios")
        elif por_barrio[bid] < MIN_NODOS_BARRIO:
            errores.append(f"el barrio {nombre} tiene {por_barrio[bid]} nodos (minimo {MIN_NODOS_BARRIO})")

    largos = sorted(c["distancia_m"] for c in calles) or [0]
    if not 280 <= len(ids) <= 320:
        avisos.append(f"el enunciado pide ~300 intersecciones y hay {len(ids)}")
    if largos[-1] > 900:
        avisos.append(f"la calle mas larga mide {largos[-1]} m (ideal <= 900 m)")
    resumen = (f"{len(ids)} nodos, {len(calles)} calles, tipos={dict(tipos)}\n"
               f"sin salida: {sin_salida} ({100 * sin_salida / len(ids):.1f} %); largo mediana "
               f"{largos[len(largos) // 2]} m, max {largos[-1]} m\n"
               f"nodos por barrio: {dict(por_barrio)}")
    return errores, avisos, resumen


if __name__ == "__main__":
    errores, avisos, resumen = validar(json.load(open(sys.argv[1], encoding="utf-8")))
    print(resumen)
    for a in avisos:
        print("AVISO:", a)
    print("\n".join(errores) or "OK")
    sys.exit(1 if errores else 0)
