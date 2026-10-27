"""Valida un grafo antes de usarlo. Uso: python tools/validar_grafo.py data/manta_graph.json"""
import collections
import json
import sys

g = json.load(open(sys.argv[1], encoding="utf-8"))
ids = {n["id"] for n in g["nodos"]}
errores = []
for c in g["calles"]:
    if c["de"] not in ids or c["a"] not in ids:
        errores.append(f"calle {c['id']} apunta a nodo inexistente")
    if c["tipo"] not in ("avenida", "calle", "callejon", "puente"):
        errores.append(f"calle {c['id']} con tipo invalido: {c['tipo']}")
    if c["distancia_m"] <= 0:
        errores.append(f"calle {c['id']} con distancia <= 0")
if len(g["refugios"]) != 4:
    errores.append(f"se esperaban 4 refugios, hay {len(g['refugios'])}")
for r in g["refugios"]:
    if r["nodo"] not in ids:
        errores.append(f"refugio {r['id']} en nodo inexistente")
adj = collections.defaultdict(set)
for c in g["calles"]:
    adj[c["de"]].add(c["a"]); adj[c["a"]].add(c["de"])
vistos, pila = set(), [g["nodos"][0]["id"]]
while pila:
    n = pila.pop()
    if n not in vistos:
        vistos.add(n); pila.extend(adj[n] - vistos)
if vistos != ids:
    errores.append(f"grafo no conexo: {len(ids) - len(vistos)} nodos inalcanzables")
tipos = collections.Counter(c["tipo"] for c in g["calles"])
print(f"{len(ids)} nodos, {len(g['calles'])} calles, tipos={dict(tipos)}")
if not 200 <= len(ids) <= 400:
    print("AVISO: el enunciado pide ~300 intersecciones")
print("\n".join(errores) or "OK")
sys.exit(1 if errores else 0)
