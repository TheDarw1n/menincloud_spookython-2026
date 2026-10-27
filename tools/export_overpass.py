"""Exporta el grafo vial REAL de Manta desde OpenStreetMap (API Overpass) a data/manta_graph.json.

Solo usa la libreria estandar de Python (sin osmnx ni networkx). Necesita internet solo la
primera vez: la respuesta cruda de Overpass queda en disco (--cache) y las corridas siguientes
no consultan la API (borra la cache para bajar datos nuevos de OSM).

Uso:
  python tools/export_overpass.py --salida data/manta_graph.json
  python tools/validar_grafo.py data/manta_graph.json

Argumentos (todos opcionales):
  --salida RUTA       JSON de salida (default: data/manta_graph.json)
  --cache DIR         carpeta de la cache cruda (default: cache_overpass/ junto a este script)
  --servidor URL      endpoint Overpass (default: https://overpass-api.de/api/interpreter)
  --descarga S,W,N,E  area que se descarga, toda la zona urbana (default: -1.005,-80.785,-0.930,-80.660)
  --bbox S,W,N,E      zona de juego, recorte local sin volver a descargar (default: -0.992,-80.772,-0.938,-80.668)
  --tolerancia M      fusiona intersecciones a menos de M metros (default: 40)
  --poda M            quita en cascada los callejones sin salida mas cortos que M metros
                      (default: inf = todos; un callejon sin salida atrapa sobrevivientes)
  --max-arista M      parte en tramos iguales las calles mas largas que M metros (default: 900)
  --sin-red           no consulta Overpass: falla si la respuesta no esta en la cache

Como se arma el grafo (~300 intersecciones):
  1. Calles: todas las motorway..tertiary (y enlaces) de la zona de juego; de las residential,
     unclassified y living_street solo las que pasan por un barrio del juego y cuyo 'trazo'
     (calle continua, aunque OSM la parta en muchas ways) mide al menos trazo_m de ese barrio.
     Las privadas (access=private/no) quedan fuera.
  2. Se unen las cadenas de nodos de grado 2 en una sola calle (largo = suma haversine).
  3. Se fusionan intersecciones cercanas (--tolerancia) sin cruzar puentes, al estilo osmnx.
  4. Se podan en cascada los callejones sin salida (--poda) y los lazos de ida y vuelta
     (calles cuyos extremos quedan a menos de --tolerancia); queda la componente conexa mayor.
  5. Calles mas largas que --max-arista (o muy curvas) se parten con nodos intermedios.
  tipo: puente si algun tramo OSM tiene bridge=yes/viaduct; si no, avenida (motorway..secondary),
  calle (tertiary/residential/unclassified) o callejon (el resto), segun los metros de cada uno.

Datos (c) colaboradores de OpenStreetMap, licencia ODbL 1.0: https://www.openstreetmap.org/copyright
"""
import argparse
import datetime
import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

SERVIDOR = "https://overpass-api.de/api/interpreter"
AGENTE = "EscapeMantaZombie/1.0 (Spookython 2026 Track A; tools/export_overpass.py)"
DESCARGA = "-1.005,-80.785,-0.930,-80.660"  # S,W,N,E: area urbana de Manta (se descarga una vez)
BBOX = (-0.992, -80.772, -0.938, -80.668)    # S, W, N, E: zona de juego (recorte local)

# tipo de calle por clase OSM (graph.py: avenida 50, calle 30, callejon 15, puente 40 km/h)
TIPO_OSM = {"motorway": "avenida", "trunk": "avenida", "primary": "avenida", "secondary": "avenida",
            "tertiary": "calle", "residential": "calle", "unclassified": "calle"}
PRINCIPALES = ("motorway", "trunk", "primary", "secondary", "tertiary")
MENORES = ("unclassified", "residential", "living_street")
RANGO = {"callejon": 0, "calle": 1, "avenida": 2, "puente": 3}

# Barrios de la historia: nodos place de OSM (consultados el 2026-10-27). Cada nodo del grafo
# va al barrio de centroide mas cercano dentro de radio_m. trazo_m: largo minimo de una calle
# menor para entrar (Barbasquillo tiene calles cortas y muchas privadas; Tarqui y Jocay, una
# cuadricula densa), ajustado para que cada barrio tenga ~35 nodos.
BARRIOS = [
    {"id": "barbasquillo", "nombre": "Barbasquillo", "lat": -0.9515404, "lng": -80.7527254,
     "radio_m": 1000, "trazo_m": 250, "osm": "node/12066773600 (place=quarter)"},
    {"id": "tarqui", "nombre": "Tarqui", "lat": -0.9532678, "lng": -80.7152080,
     "radio_m": 900, "trazo_m": 800, "osm": "node/13095205932 (place=neighbourhood, Tarqui Centro)"},
    {"id": "jocay", "nombre": "Jocay", "lat": -0.9598756, "lng": -80.7161161,
     "radio_m": 900, "trazo_m": 700, "osm": "node/13111139050 (place=neighbourhood)"},
    {"id": "los-esteros", "nombre": "Los Esteros", "lat": -0.9621547, "lng": -80.6922764,
     "radio_m": 1100, "trazo_m": 450, "osm": "node/10213104582 (place=suburb)"},
]

# Refugios en lugares reales (centro del objeto OSM, consultado el 2026-10-27)
REFUGIOS = [
    {"id": "R-1", "nombre": "Universidad Laica Eloy Alfaro de Manabí (ULEAM)",
     "lat": -0.95267, "lng": -80.74528, "osm": "way/851414676"},
    {"id": "R-2", "nombre": "Estadio Jocay", "lat": -0.96397, "lng": -80.70275,
     "osm": "relation/17836148"},
    {"id": "R-3", "nombre": "Hospital General IESS Manta", "lat": -0.98489, "lng": -80.69404,
     "osm": "way/678145288"},
    {"id": "R-4", "nombre": "Colegio Réplica Manta", "lat": -0.98137, "lng": -80.71950,
     "osm": "way/427131500"},
]


# ---------- descarga ----------
def consulta_overpass(area=DESCARGA):
    """Todas las vias de autos del area (tambien service/track, por si se quieren usar luego)."""
    clases = f'^(({"|".join(PRINCIPALES)})(_link)?|{"|".join(MENORES)}|service|road|track)$'
    return f'[out:json][timeout:300];\nway["highway"~"{clases}"]({area});\nout geom;\n'


def descargar(consulta, cache, servidor=SERVIDOR, sin_red=False, intentos=6):
    """Respuesta cruda de Overpass, cacheada en disco por hash de la consulta. Reintenta con
    espera exponencial (el servidor publico responde 429/504 cuando esta saturado)."""
    ruta = Path(cache) / f"overpass_{hashlib.sha1(consulta.encode()).hexdigest()[:12]}.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    if sin_red:
        sys.exit(f"no hay cache en {ruta} y se pidio --sin-red")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = urllib.parse.urlencode({"data": consulta}).encode()
    espera = 30
    for i in range(intentos):
        peticion = urllib.request.Request(servidor, data=datos, headers={"User-Agent": AGENTE})
        try:
            with urllib.request.urlopen(peticion, timeout=360) as r:
                crudo = r.read().decode("utf-8")
            respuesta = json.loads(crudo)
            if "remark" in respuesta:  # error de ejecucion de Overpass: datos incompletos
                raise ValueError(respuesta["remark"])
            ruta.write_text(crudo, encoding="utf-8")
            return respuesta
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                sys.exit(f"Overpass respondio HTTP {e.code}; revisa la consulta o el --servidor")
            error = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ValueError) as e:  # JSONDecodeError es ValueError
            error = e
        print(f"Overpass intento {i + 1}/{intentos} fallo ({error}); espero {espera} s", file=sys.stderr)
        time.sleep(espera)
        espera *= 2
    sys.exit("Overpass no respondio; prueba mas tarde o con otro --servidor")


# ---------- geometria ----------
def haversine(a, b):
    """Metros entre dos puntos (lat, lng)."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def largo_linea(puntos):
    return sum(haversine(p, q) for p, q in zip(puntos, puntos[1:]))


# ---------- grafo ----------
class Tramo:
    """Calle entre los nodos a y b: puntos (lat, lng) de a hasta b y, por cada segmento entre
    dos puntos, su (tipo, nombre). El largo es el de la linea (suma haversine)."""
    __slots__ = ("a", "b", "puntos", "segs", "largo")

    def __init__(self, a, b, puntos, segs):
        self.a, self.b, self.puntos, self.segs = a, b, puntos, segs
        self.largo = largo_linea(puntos)

    def desde(self, n):
        """(puntos, segs) recorridos desde el nodo n."""
        return (self.puntos, self.segs) if n == self.a else (self.puntos[::-1], self.segs[::-1])

    @property
    def es_puente(self):
        return any(tipo == "puente" for tipo, _ in self.segs)

    def _por_largo(self, campo):
        total = Counter()
        for p, q, seg in zip(self.puntos, self.puntos[1:], self.segs):
            if seg[campo]:
                total[seg[campo]] += haversine(p, q) + 1e-6
        return total

    @property
    def tipo(self):
        """puente si algun segmento es puente; si no, el tipo con mas metros."""
        if self.es_puente:
            return "puente"
        metros = self._por_largo(0)
        return max(metros, key=lambda t: (metros[t], RANGO[t]))

    @property
    def nombre(self):
        metros = self._por_largo(1)
        return metros.most_common(1)[0][0] if metros else None


class Grafo:
    """Grafo no dirigido simple: a lo mas una calle por par de nodos (la mas corta)."""

    def __init__(self):
        self.pos = {}                     # nodo -> (lat, lng)
        self.ady = defaultdict(dict)      # nodo -> {vecino: Tramo}

    def agregar(self, t):
        if t.a == t.b:
            return
        previo = self.ady[t.a].get(t.b)
        if previo is None or t.largo < previo.largo:
            self.ady[t.a][t.b] = self.ady[t.b][t.a] = t

    def quitar_nodo(self, v):
        for u in self.ady.pop(v, {}):
            self.ady[u].pop(v, None)
        self.pos.pop(v, None)

    def tramos(self):
        return list({id(t): t for vec in self.ady.values() for t in vec.values()}.values())

    def componentes(self):
        resto, comps = set(self.ady), []
        while resto:
            comp, pila = set(), [resto.pop()]
            while pila:
                u = pila.pop()
                comp.add(u)
                pila += [v for v in self.ady[u] if v in resto]
                resto.difference_update(self.ady[u])
            comps.append(comp)
        return comps

    def dejar_componente_mayor(self):
        mayor = max(self.componentes(), key=len)
        for v in [v for v in self.ady if v not in mayor]:
            self.quitar_nodo(v)


def tipo_via(tags):
    if tags.get("bridge") in ("yes", "viaduct"):
        return "puente"
    return TIPO_OSM.get(tags["highway"].replace("_link", ""), "callejon")


def rumbo(p, q):
    """Rumbo en grados de p hacia q (0 = norte)."""
    return math.degrees(math.atan2((q[1] - p[1]) * math.cos(math.radians(p[0])), q[0] - p[0]))


def trazos(ways):
    """Largo del 'trazo' (stroke) de cada way: las ways se encadenan en sus extremos con la que
    sigue mas recta (desvio <= 30 grados, o <= 60 si tienen el mismo nombre). Asi una calle
    partida en muchas ways cuenta con su largo real. Devuelve {id_way: metros del trazo}."""
    largo, padre, extremos = {}, {}, defaultdict(list)
    for w in ways:
        pts = [(p["lat"], p["lon"]) for p in w["geometry"]]
        largo[w["id"]], padre[w["id"]] = largo_linea(pts), w["id"]
        nombre = w["tags"].get("name")
        extremos[w["nodes"][0]].append((w["id"], rumbo(pts[0], pts[1]), nombre))
        extremos[w["nodes"][-1]].append((w["id"], rumbo(pts[-1], pts[-2]), nombre))

    def raiz(x):
        while padre[x] != x:
            padre[x] = x = padre[padre[x]]
        return x

    for llegan in extremos.values():
        pares = []
        for i, (wi, ri, ni) in enumerate(llegan):
            for j, (wj, rj, nj) in enumerate(llegan[:i]):
                if wi == wj or (ni and nj and ni != nj):
                    continue
                desvio = 180 - abs((ri - rj + 180) % 360 - 180)
                if desvio <= (60 if ni and ni == nj else 30):
                    pares.append((desvio, i, j))
        usados = set()
        for _, i, j in sorted(pares):
            if i not in usados and j not in usados:
                usados |= {i, j}
                padre[raiz(llegan[i][0])] = raiz(llegan[j][0])
    total = Counter()
    for w, metros in largo.items():
        total[raiz(w)] += metros
    return {w: total[raiz(w)] for w in largo}


def seleccionar(ways, barrios):
    """Entran todas las motorway..tertiary (y enlaces). De las calles menores solo las que
    tocan el radio de un barrio del juego y cuyo trazo mide >= trazo_m de ese barrio (calles
    de paso, no pasajes). Las privadas (access=private/no) quedan fuera."""
    publicas = [w for w in ways if w["tags"].get("access") not in ("private", "no")
                and w["tags"].get("area") != "yes"]
    largo = trazos([w for w in publicas if w["tags"]["highway"] in MENORES])

    def en_barrio(w):
        return any(largo[w["id"]] >= b["trazo_m"] and haversine((p["lat"], p["lon"]), (b["lat"], b["lng"])) <= b["radio_m"]
                   for b in barrios for p in w["geometry"])

    return [w for w in publicas
            if w["tags"]["highway"].replace("_link", "") in PRINCIPALES or (w["id"] in largo and en_barrio(w))]


def grafo_osm(ways, bbox):
    """Grafo nodo a nodo de OSM con los segmentos que caen dentro de la zona de juego."""
    s, o, n, e = bbox
    dentro = lambda p: s <= p[0] <= n and o <= p[1] <= e
    g = Grafo()
    for w in ways:
        seg = (tipo_via(w["tags"]), w["tags"].get("name"))
        puntos = [(p["lat"], p["lon"]) for p in w["geometry"]]
        for a, b, pa, pb in zip(w["nodes"], w["nodes"][1:], puntos, puntos[1:]):
            if dentro(pa) and dentro(pb):
                g.pos[a], g.pos[b] = pa, pb
                g.agregar(Tramo(a, b, [pa, pb], [seg]))
    g.dejar_componente_mayor()
    return g


def contraer(g):
    """Une cada cadena de nodos de grado 2 en una sola calle. Devuelve cuantos nodos quito."""
    quitados = 0
    pendientes = [v for v in g.ady if len(g.ady[v]) == 2]
    while pendientes:
        v = pendientes.pop()
        if len(g.ady.get(v, ())) != 2:
            continue
        (u, t1), (w, t2) = g.ady[v].items()
        p1, s1 = t1.desde(u)
        p2, s2 = t2.desde(v)
        g.quitar_nodo(v)
        g.agregar(Tramo(u, w, p1 + p2[1:], s1 + s2))
        quitados += 1
        pendientes += [x for x in (u, w) if len(g.ady[x]) == 2]
    return quitados


def podar(g, largo_max):
    """Quita los callejones sin salida (grado 1) mas cortos que largo_max."""
    quitados = 0
    for v in [v for v, vec in g.ady.items() if len(vec) == 1]:
        vec = g.ady.get(v, {})
        if len(vec) == 1 and next(iter(vec.values())).largo < largo_max:
            g.quitar_nodo(v)
            quitados += 1
    return quitados


def conectados(g, a, b):
    vistos, pila = {a}, [a]
    while pila:
        u = pila.pop()
        if u == b:
            return True
        nuevos = [v for v in g.ady[u] if v not in vistos]
        vistos.update(nuevos)
        pila += nuevos
    return False


def quitar_lazos(g, tol, largo_max):
    """Quita las calles que salen y vuelven casi al mismo punto (extremos a <= tol metros), como
    las dos calzadas de una avenida que se unen fuera de la zona de juego: en el juego son un
    callejon sin salida de ida y vuelta. Solo si sus extremos siguen unidos por otro camino."""
    quitados = 0
    for t in g.tramos():
        if 4 * tol < t.largo < 2 * largo_max and haversine(g.pos[t.a], g.pos[t.b]) <= tol:
            del g.ady[t.a][t.b], g.ady[t.b][t.a]
            if conectados(g, t.a, t.b):
                quitados += 1
            else:
                g.agregar(t)
    return quitados


def consolidar(g, tol):
    """Fusiona intersecciones a <= tol metros de un nodo lider (sin encadenar grupos), al estilo
    de osmnx.consolidate_intersections. Solo se fusionan nodos unidos entre si por calles internas
    que no son puente, para no 'saltar' un rio. El nodo fusionado queda en el centroide."""
    celda = tol / 111000
    rejilla = defaultdict(list)
    for v, (la, ln) in g.pos.items():
        rejilla[(int(la // celda), int(ln // celda))].append(v)
    grupo = {}
    for v in sorted(g.ady, key=lambda v: (-len(g.ady[v]), v)):
        if v in grupo:
            continue
        ci, cj = int(g.pos[v][0] // celda), int(g.pos[v][1] // celda)
        cerca = {x for i in (-1, 0, 1) for j in (-1, 0, 1) for x in rejilla[(ci + i, cj + j)]
                 if x not in grupo and haversine(g.pos[v], g.pos[x]) <= tol}
        grupo[v], pila = v, [v]
        while pila:
            u = pila.pop()
            for x, t in g.ady[u].items():
                if x in cerca and x not in grupo and not t.es_puente:
                    grupo[x] = v
                    pila.append(x)
    miembros = defaultdict(list)
    for x, lider in grupo.items():
        miembros[lider].append(g.pos[x])
    nuevo = Grafo()
    for lider, pts in miembros.items():
        nuevo.pos[lider] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    for t in g.tramos():
        a, b = grupo[t.a], grupo[t.b]
        if a != b:
            nuevo.agregar(Tramo(a, b, [nuevo.pos[a]] + t.puntos[1:-1] + [nuevo.pos[b]], t.segs))
    for v in [v for v in nuevo.pos if not nuevo.ady[v]]:
        nuevo.quitar_nodo(v)
    return nuevo


def partir_largas(g, max_m):
    """Parte cada calle mas larga que max_m en k tramos iguales siguiendo su geometria, y en 2
    las muy curvas (largo > 2.5 x la recta), porque el mapa del juego dibuja rectas entre nodos.
    Agrega nodos intermedios; cada tramo conserva el tipo de sus propios segmentos."""
    nuevo_id = -1
    for t in g.tramos():
        k = math.ceil(t.largo / max_m)
        if k == 1 and t.largo > 300 and t.largo > 2.5 * haversine(t.puntos[0], t.puntos[-1]):
            k = 2
        if k <= 1:
            continue
        del g.ady[t.a][t.b], g.ady[t.b][t.a]
        paso, falta, cortes = t.largo / k, t.largo / k, 0
        previo, pts, segs = t.a, [t.puntos[0]], []
        for p, q, seg in zip(t.puntos, t.puntos[1:], t.segs):
            d = haversine(p, q)
            while cortes < k - 1 and d >= falta:
                f = falta / d
                m = (p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1]))
                g.pos[nuevo_id] = m
                g.agregar(Tramo(previo, nuevo_id, pts + [m], segs + [seg]))
                previo, nuevo_id, cortes = nuevo_id, nuevo_id - 1, cortes + 1
                pts, segs, p, d, falta = [m], [], m, d - falta, paso
            pts.append(q)
            segs.append(seg)
            falta -= d
        g.agregar(Tramo(previo, t.b, pts, segs))


def construir(ways, bbox=BBOX, tolerancia=40, poda=math.inf, max_arista=900, barrios=BARRIOS):
    g = grafo_osm(seleccionar(ways, barrios), bbox)
    contraer(g)
    g = consolidar(g, tolerancia)
    while podar(g, poda) + quitar_lazos(g, tolerancia, poda) + contraer(g):
        pass
    g.dejar_componente_mayor()
    partir_largas(g, max_arista)
    return g


# ---------- salida ----------
def barrio_de(p, barrios):
    """Id del barrio con el centroide mas cercano dentro de su radio, o 'otro'."""
    cerca = [(haversine(p, (b["lat"], b["lng"])), b["id"]) for b in barrios]
    cerca = [(d, i) for (d, i), b in zip(cerca, barrios) if d <= b["radio_m"]]
    return min(cerca)[1] if cerca else "otro"


def a_json(g, fuente, barrios=BARRIOS, refugios=REFUGIOS):
    orden = sorted(g.ady, key=lambda v: (g.pos[v][1], g.pos[v][0]))  # de oeste a este
    ids = {v: f"N-{i:04d}" for i, v in enumerate(orden, 1)}
    nodos = [{"id": ids[v], "lat": round(g.pos[v][0], 6), "lng": round(g.pos[v][1], 6),
              "barrio": barrio_de(g.pos[v], barrios)} for v in orden]
    calles = []
    for t in sorted(g.tramos(), key=lambda t: tuple(sorted((ids[t.a], ids[t.b])))):
        de, a = sorted((ids[t.a], ids[t.b]))
        calle = {"id": "", "de": de, "a": a, "distancia_m": max(1, round(t.largo)), "tipo": t.tipo}
        if t.nombre:
            calle["nombre"] = t.nombre
        calles.append(calle)
    for i, c in enumerate(calles, 1):
        c["id"] = f"E-{i:04d}"
    usados, salida_refugios = set(), []
    for r in refugios:
        v = min((v for v in orden if v not in usados), key=lambda v: haversine(g.pos[v], (r["lat"], r["lng"])))
        usados.add(v)
        salida_refugios.append({"id": r["id"], "nodo": ids[v], "nombre": r["nombre"], "lat": r["lat"],
                                "lng": r["lng"], "osm": r["osm"],
                                "distancia_nodo_m": round(haversine(g.pos[v], (r["lat"], r["lng"])))})
    por_barrio = Counter(n["barrio"] for n in nodos)
    salida_barrios = [{"id": b["id"], "nombre": b["nombre"], "lat": round(b["lat"], 6), "lng": round(b["lng"], 6),
                       "radio_m": b["radio_m"], "osm": b["osm"], "nodos": por_barrio[b["id"]]} for b in barrios]
    return {"_fuente": fuente, "barrios": salida_barrios, "nodos": nodos, "calles": calles,
            "refugios": salida_refugios}


def escribir(datos, ruta):
    """JSON legible y compacto: un elemento por linea."""
    lineas = ["{"]
    claves = list(datos)
    for k in claves:
        fin = "," if k != claves[-1] else ""
        valor = datos[k]
        if isinstance(valor, list):
            cuerpo = ",\n".join("  " + json.dumps(x, ensure_ascii=False) for x in valor)
            lineas.append(f' "{k}": [\n{cuerpo}\n ]{fin}')
        else:
            lineas.append(f' "{k}": {json.dumps(valor, ensure_ascii=False)}{fin}')
    lineas.append("}")
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text("\n".join(lineas) + "\n", encoding="utf-8")


def resumen(datos):
    nodos, calles = datos["nodos"], datos["calles"]
    grado = Counter()
    for c in calles:
        grado[c["de"]] += 1
        grado[c["a"]] += 1
    largos = sorted(c["distancia_m"] for c in calles)
    sin_salida = sum(1 for n in nodos if grado[n["id"]] == 1)
    print(f"{len(nodos)} nodos, {len(calles)} calles; tipos={dict(Counter(c['tipo'] for c in calles))}")
    print(f"sin salida: {sin_salida} ({100 * sin_salida / len(nodos):.1f} %); "
          f"largo mediana {largos[len(largos) // 2]} m, max {largos[-1]} m")
    print("nodos por barrio:", dict(Counter(n["barrio"] for n in nodos)))
    for r in datos["refugios"]:
        print(f"  {r['id']} {r['nombre']} -> {r['nodo']} ({r['distancia_nodo_m']} m)")


def main(args):
    bbox = tuple(float(x) for x in args.bbox.split(","))
    consulta = consulta_overpass(args.descarga)
    crudo = descargar(consulta, args.cache, args.servidor, args.sin_red)
    ways = [e for e in crudo["elements"] if e["type"] == "way"]
    g = construir(ways, bbox, args.tolerancia, args.poda, args.max_arista)
    fuente = {
        "datos": "© colaboradores de OpenStreetMap, licencia ODbL 1.0 (https://www.openstreetmap.org/copyright)",
        "overpass": args.servidor, "osm_base": crudo["osm3s"]["timestamp_osm_base"],
        "generado": datetime.date.today().isoformat(),
        "comando": "python tools/export_overpass.py " + " ".join(sys.argv[1:]),
        "parametros": {"descarga": args.descarga, "bbox": list(bbox), "tolerancia_m": args.tolerancia,
                       "poda_m": args.poda if math.isfinite(args.poda) else "todos",
                       "max_arista_m": args.max_arista,
                       "trazo_m": {b["id"]: b["trazo_m"] for b in BARRIOS}},
    }
    datos = a_json(g, fuente)
    escribir(datos, args.salida)
    resumen(datos)
    print("->", args.salida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Exporta el grafo de Manta desde OSM (Overpass)")
    ap.add_argument("--salida", default="data/manta_graph.json")
    ap.add_argument("--cache", default=str(Path(__file__).resolve().parent / "cache_overpass"))
    ap.add_argument("--servidor", default=SERVIDOR)
    ap.add_argument("--descarga", default=DESCARGA, help="S,W,N,E del area que se descarga")
    ap.add_argument("--bbox", default=",".join(map(str, BBOX)), help="S,W,N,E de la zona de juego")
    ap.add_argument("--tolerancia", type=float, default=40)
    ap.add_argument("--poda", type=float, default=math.inf)
    ap.add_argument("--max-arista", type=float, default=900)
    ap.add_argument("--sin-red", action="store_true")
    main(ap.parse_args())
