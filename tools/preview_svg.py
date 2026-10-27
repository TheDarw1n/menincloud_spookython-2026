"""Dibuja un grafo del juego (manta_graph.json) como SVG puro, para revisarlo sin servidor.
Uso: python tools/preview_svg.py data/manta_graph.json grafo_manta.svg"""
import json
import math
import sys
from collections import Counter
from html import escape

ANCHO, MARGEN, CABECERA, PIE = 1600, 36, 78, 118
TINTA, TINTA_2, TENUE, BORDE = "#0b0b0b", "#52514e", "#898781", "#c3c2b7"
# paleta categorica validada (orange, blue, aqua) + gris neutro para callejon
ESTILO = {  # tipo: (color, grosor, etiqueta)
    "callejon": (TENUE, 1.2, "callejón · 15 km/h"),
    "calle": ("#2a78d6", 1.8, "calle · 30 km/h"),
    "avenida": ("#eb6834", 3.2, "avenida · 50 km/h"),
    "puente": ("#1baf7a", 4.6, "puente · 40 km/h"),
}
FUENTE = 'font-family="system-ui, -apple-system, Segoe UI, sans-serif"'


def texto(x, y, s, tam=13, color=TINTA, peso="normal", ancla="start", halo=True):
    h = ' stroke="#ffffff" stroke-width="3.5" paint-order="stroke" stroke-linejoin="round"' if halo else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{tam}" fill="{color}" font-weight="{peso}" '
            f'text-anchor="{ancla}"{h}>{escape(s)}</text>')


def main(entrada, salida):
    g = json.load(open(entrada, encoding="utf-8"))
    nodos = {n["id"]: n for n in g["nodos"]}
    barrios = g.get("barrios", [])
    lats = [n["lat"] for n in g["nodos"]] + [r["lat"] for r in g["refugios"]]
    lngs = [n["lng"] for n in g["nodos"]] + [r["lng"] for r in g["refugios"]]
    lat0 = (max(lats) + min(lats)) / 2
    kx = math.cos(math.radians(lat0))
    for b in barrios:  # que los circulos de los barrios entren completos
        dlat, dlng = b["radio_m"] / 111320, b["radio_m"] / (111320 * kx)
        lats += [b["lat"] - dlat, b["lat"] + dlat]
        lngs += [b["lng"] - dlng, b["lng"] + dlng]
    escala = (ANCHO - 2 * MARGEN) / ((max(lngs) - min(lngs)) * kx)        # px por grado
    alto_mapa = (max(lats) - min(lats)) * escala
    alto = CABECERA + alto_mapa + PIE + 2 * MARGEN
    px_m = escala / 111320                                                 # px por metro
    xy = lambda lat, lng: (MARGEN + (lng - min(lngs)) * kx * escala, CABECERA + MARGEN + (max(lats) - lat) * escala)

    grado = Counter()
    for c in g["calles"]:
        grado[c["de"]] += 1
        grado[c["a"]] += 1
    tipos = Counter(c["tipo"] for c in g["calles"])
    sin_salida = [i for i in nodos if grado[i] == 1]

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{alto:.0f}" '
         f'viewBox="0 0 {ANCHO} {alto:.0f}" {FUENTE}>',
         f'<rect width="100%" height="100%" fill="#ffffff"/>']
    # barrios: circulo del radio usado + etiqueta
    for b in barrios:
        x, y = xy(b["lat"], b["lng"])
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{b["radio_m"] * px_m:.1f}" fill="#f0efec" '
                 f'fill-opacity="0.65" stroke="{BORDE}" stroke-width="1"><title>{escape(b["nombre"])}: '
                 f'radio {b["radio_m"]} m</title></circle>')
    # calles por tipo (los puentes encima, con borde oscuro para que resalten)
    for tipo in ("callejon", "calle", "avenida", "puente"):
        color, grosor, _ = ESTILO[tipo]
        for c in (c for c in g["calles"] if c["tipo"] == tipo):
            (x1, y1), (x2, y2) = xy(nodos[c["de"]]["lat"], nodos[c["de"]]["lng"]), xy(nodos[c["a"]]["lat"], nodos[c["a"]]["lng"])
            info = escape(f'{c["id"]} · {c.get("nombre") or "sin nombre"} · {tipo} · {c["distancia_m"]} m')
            if tipo == "puente":
                o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{TINTA}" '
                         f'stroke-width="{grosor + 2.4}" stroke-linecap="round"/>')
            o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
                     f'stroke-width="{grosor}" stroke-linecap="round"><title>{info}</title></line>')
    # nodos (sin salida: aro hueco)
    for i, n in nodos.items():
        x, y = xy(n["lat"], n["lng"])
        info = escape(f'{i} · barrio {n.get("barrio", "?")} · grado {grado[i]}')
        if grado[i] == 1:
            o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="#ffffff" stroke="{TINTA}" stroke-width="1.4">'
                     f'<title>{info} (sin salida)</title></circle>')
        else:
            o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{TINTA_2}"><title>{info}</title></circle>')
    # etiquetas de barrios: arriba del circulo, o abajo si arriba cae dentro de otro barrio
    for b in barrios:
        x, y = xy(b["lat"], b["lng"])
        r = b["radio_m"] * px_m
        tapado = any(math.dist((x, y - r), xy(o_["lat"], o_["lng"])) < o_["radio_m"] * px_m
                     for o_ in barrios if o_ is not b)
        y_txt = y + r + 22 if tapado else y - r - 24
        cuantos = sum(1 for n in g["nodos"] if n.get("barrio") == b["id"])
        o.append(texto(x, y_txt, b["nombre"].upper(), 15, TINTA, "700", "middle"))
        o.append(texto(x, y_txt + 16, f"{cuantos} nodos", 12, TINTA_2, "normal", "middle"))
    # refugios: lugar real (rombo) unido a su nodo (cuadro con el numero)
    for r in g["refugios"]:
        n = nodos[r["nodo"]]
        (xl, yl), (xn, yn) = xy(r["lat"], r["lng"]), xy(n["lat"], n["lng"])
        o.append(f'<line x1="{xl:.1f}" y1="{yl:.1f}" x2="{xn:.1f}" y2="{yn:.1f}" stroke="{TINTA}" stroke-width="1.2"/>')
        o.append(f'<path d="M{xl:.1f},{yl - 6:.1f} l6,6 l-6,6 l-6,-6 z" fill="#ffffff" stroke="{TINTA}" stroke-width="1.4"/>')
        o.append(f'<rect x="{xn - 11:.1f}" y="{yn - 11:.1f}" width="22" height="22" rx="4" fill="{TINTA}">'
                 f'<title>{escape(r["id"] + " · " + r["nombre"] + " · " + r["nodo"])}</title></rect>')
        o.append(texto(xn, yn + 4.5, r["id"].replace("R-", "R"), 11, "#ffffff", "700", "middle", halo=False))
        o.append(texto(xn + 15, yn - 6, r["nombre"], 13, TINTA, "600"))
        o.append(texto(xn + 15, yn + 10, f'{r["id"]} · nodo {r["nodo"]}', 11, TINTA_2))
    # cabecera
    fuente = g.get("_fuente", {})
    o.append(texto(MARGEN, 34, "Grafo vial de Manta · Escape de Manta Zombie", 22, TINTA, "700", halo=False))
    o.append(texto(MARGEN, 58, f'{len(nodos)} intersecciones · {len(g["calles"])} calles · '
                   f'{tipos["puente"]} puentes · {tipos["avenida"]} avenidas · {len(sin_salida)} sin salida '
                   f'({100 * len(sin_salida) / len(nodos):.1f} %) · {len(g["refugios"])} refugios', 14, TINTA_2, halo=False))
    # pie: leyenda + escala + atribucion
    y0 = alto - PIE + 14
    x = MARGEN
    for tipo in ("avenida", "calle", "callejon", "puente"):
        color, grosor, etiqueta = ESTILO[tipo]
        if tipo == "puente":
            o.append(f'<line x1="{x}" y1="{y0}" x2="{x + 34}" y2="{y0}" stroke="{TINTA}" stroke-width="{grosor + 2.4}" stroke-linecap="round"/>')
        o.append(f'<line x1="{x}" y1="{y0}" x2="{x + 34}" y2="{y0}" stroke="{color}" stroke-width="{grosor}" stroke-linecap="round"/>')
        o.append(texto(x + 42, y0 + 4.5, f"{etiqueta} ({tipos[tipo]})", 13, TINTA, halo=False))
        x += 250
    y1 = y0 + 30
    o.append(f'<circle cx="{MARGEN + 6}" cy="{y1}" r="2.4" fill="{TINTA_2}"/>')
    o.append(texto(MARGEN + 16, y1 + 4.5, "intersección", 13, halo=False))
    o.append(f'<circle cx="{MARGEN + 136}" cy="{y1}" r="3.6" fill="#ffffff" stroke="{TINTA}" stroke-width="1.4"/>')
    o.append(texto(MARGEN + 146, y1 + 4.5, "sin salida", 13, halo=False))
    o.append(f'<rect x="{MARGEN + 245}" y="{y1 - 9}" width="18" height="18" rx="3" fill="{TINTA}"/>')
    o.append(f'<path d="M{MARGEN + 280},{y1 - 6} l6,6 l-6,6 l-6,-6 z" fill="#ffffff" stroke="{TINTA}" stroke-width="1.4"/>')
    o.append(texto(MARGEN + 292, y1 + 4.5, "refugio: nodo del juego (cuadro) y lugar real (rombo)", 13, halo=False))
    o.append(f'<circle cx="{MARGEN + 690}" cy="{y1}" r="9" fill="#f0efec" stroke="{BORDE}"/>')
    o.append(texto(MARGEN + 705, y1 + 4.5, "barrio (radio usado; cada nodo va al centroide más cercano)", 13, halo=False))
    # barra de escala de 1 km
    xb, yb = ANCHO - MARGEN - 1000 * px_m, y1 + 30
    o.append(f'<line x1="{xb:.1f}" y1="{yb}" x2="{ANCHO - MARGEN}" y2="{yb}" stroke="{TINTA}" stroke-width="2"/>')
    o.append(f'<line x1="{xb:.1f}" y1="{yb - 5}" x2="{xb:.1f}" y2="{yb + 5}" stroke="{TINTA}" stroke-width="2"/>')
    o.append(f'<line x1="{ANCHO - MARGEN}" y1="{yb - 5}" x2="{ANCHO - MARGEN}" y2="{yb + 5}" stroke="{TINTA}" stroke-width="2"/>')
    o.append(texto(xb + 500 * px_m, yb - 8, "1 km", 12, TINTA, "600", "middle", halo=False))
    o.append(texto(MARGEN, y1 + 36, f'Datos © colaboradores de OpenStreetMap (ODbL) · base OSM {fuente.get("osm_base", "?")} · '
                   f'calles dibujadas como recta entre nodos, igual que en el juego', 12, TINTA_2, halo=False))
    o.append("</svg>")
    open(salida, "w", encoding="utf-8").write("\n".join(o))
    print(f"{salida}: {len(nodos)} nodos, {len(g['calles'])} calles")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
