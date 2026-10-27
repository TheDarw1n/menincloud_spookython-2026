"""Exporta Manta desde OpenStreetMap a data/manta_graph.json (~300 nodos). Se corre UNA vez,
en un PC con internet (no en produccion). SIN PROBAR: ajusta TOLERANCIA hasta ~300 nodos.
  pip install -r tools/requirements-tools.txt
  python tools/export_manta.py --tolerancia 60 --salida data/manta_graph.json
  python tools/validar_grafo.py data/manta_graph.json
"""
import argparse
import json

import networkx as nx
import osmnx as ox

TIPO = {"motorway": "avenida", "trunk": "avenida", "primary": "avenida", "secondary": "avenida",
        "motorway_link": "avenida", "trunk_link": "avenida", "primary_link": "avenida",
        "secondary_link": "avenida", "tertiary": "calle", "tertiary_link": "calle",
        "residential": "calle", "unclassified": "calle"}


def tipo_calle(d):
    if str(d.get("bridge", "no")).lower() not in ("no", "nan", "none"):
        return "puente"
    hw = d.get("highway")
    hw = hw[0] if isinstance(hw, list) else hw
    return TIPO.get(hw, "callejon")


def main(a):
    g = ox.graph_from_place(a.lugar, network_type="drive")
    g = ox.project_graph(g)
    g = ox.consolidate_intersections(g, tolerance=a.tolerancia, rebuild_graph=True, dead_ends=False)
    g = ox.project_graph(g, to_crs="EPSG:4326")
    u = nx.Graph()
    for n, d in g.nodes(data=True):
        u.add_node(n, lat=d["y"], lng=d["x"])
    for a_, b_, d in g.edges(data=True):
        if a_ == b_:
            continue
        L = float(d.get("length", 0)) or 1.0
        if not u.has_edge(a_, b_) or L < u[a_][b_]["L"]:
            u.add_edge(a_, b_, L=L, tipo=tipo_calle(d))
    u = u.subgraph(max(nx.connected_components(u), key=len)).copy()
    ids = {n: f"N-{i:04d}" for i, n in enumerate(sorted(u.nodes), 1)}
    nodos = [{"id": ids[n], "lat": round(u.nodes[n]["lat"], 6), "lng": round(u.nodes[n]["lng"], 6)} for n in u.nodes]
    calles = [{"id": f"E-{i:04d}", "de": ids[x], "a": ids[y], "distancia_m": round(d["L"]),
               "tipo": d["tipo"]} for i, (x, y, d) in enumerate(u.edges(data=True), 1)]
    # 4 refugios: el nodo mas cercano al centro de cada cuadrante del mapa
    lat0 = sum(n["lat"] for n in nodos) / len(nodos)
    lng0 = sum(n["lng"] for n in nodos) / len(nodos)
    refugios = []
    for k, (sl, sg) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)], 1):
        cuad = [n for n in nodos if (n["lat"] - lat0) * sl >= 0 and (n["lng"] - lng0) * sg >= 0] or nodos
        cl = sum(n["lat"] for n in cuad) / len(cuad)
        cg = sum(n["lng"] for n in cuad) / len(cuad)
        mejor = min(cuad, key=lambda n: (n["lat"] - cl) ** 2 + (n["lng"] - cg) ** 2)
        refugios.append({"id": f"R-{k}", "nodo": mejor["id"]})
    json.dump({"nodos": nodos, "calles": calles, "refugios": refugios},
              open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(nodos)} nodos, {len(calles)} calles -> {a.salida}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lugar", default="Manta, Manabí, Ecuador")
    ap.add_argument("--tolerancia", type=float, default=60, help="metros para fusionar intersecciones")
    ap.add_argument("--salida", default="data/manta_graph.json")
    main(ap.parse_args())
