"""Dibuja arquitectura.svg con el mismo modelo de gen_drawio.py (mismas cajas, flechas y numeros).

Uso: python gen_svg.py [salida.svg]
Los atributos data-* solo sirven para que verificar.py detecte textos encimados o cortados.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from gen_drawio import (ACCESO, ALTO, ANCHO, CAJA_FLUJOS, CAJAS, CATEGORIAS, COLOR_CONTENEDOR, FLECHAS, FLUJOS,
                        FUENTE, FUENTE_MONO, GRUPOS, LEYENDA, LINEAS, NOTA, PESTANAS, PRO, SUBTITULO, TITULO,
                        ancho_texto, linea)

TINTA, TEXTO, SUAVE = "#16191F", "#333D47", "#545B64"


def esc(t):
    return escape(str(t), {'"': "&quot;"})


class Lienzo:
    def __init__(self):
        self.partes = []

    def add(self, s):
        self.partes.append(s)

    def texto(self, x, y, t, tam=12, negrita=False, color=TEXTO, mono=False, ancla="start", dueno=None,
              rol="texto", halo=False, extra=""):
        attrs = f'x="{x:g}" y="{y:g}" font-size="{tam}" fill="{color}"'
        if negrita:
            attrs += ' font-weight="bold"'
        if mono:
            attrs += f' font-family="{FUENTE_MONO}"'
        if ancla != "start":
            attrs += f' text-anchor="{ancla}"'
        if halo:
            attrs += ' stroke="#FFFFFF" stroke-width="4" stroke-linejoin="round" paint-order="stroke"'
        if dueno:
            attrs += f' data-dueno="{dueno}"'
        self.add(f'<text {attrs} data-rol="{rol}"{extra}>{esc(t)}</text>')

    def rect(self, x, y, w, h, rid=None, tipo="caja", rx=8, relleno="#FFFFFF", borde="none", grosor=1, guiones=None):
        attrs = f'x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx}" fill="{relleno}"'
        if borde != "none":
            attrs += f' stroke="{borde}" stroke-width="{grosor}"'
        if guiones:
            attrs += f' stroke-dasharray="{guiones}"'
        if rid:
            attrs += f' data-rect="{rid}" data-tipo="{tipo}"'
        self.add(f"<rect {attrs}/>")


# ---------------------------------------------------------------- piezas basicas
def glifo(sv, clave, gx, gy, color):
    """Iconos de 10 px: globo (publico), llave (API key), candado (privado)."""
    if clave == "publico":
        sv.add(f'<g fill="none" stroke="{color}" stroke-width="1.1"><circle cx="{gx + 5}" cy="{gy + 5}" r="4.4"/>'
               f'<ellipse cx="{gx + 5}" cy="{gy + 5}" rx="1.9" ry="4.4"/>'
               f'<path d="M{gx + 0.6} {gy + 5}h8.8"/></g>')
    elif clave == "clave":
        sv.add(f'<g fill="none" stroke="{color}" stroke-width="1.3"><circle cx="{gx + 2.8}" cy="{gy + 5}" r="2.3"/>'
               f'<path d="M{gx + 5.1} {gy + 5}h4.6M{gx + 8} {gy + 5}v2.2M{gx + 9.6} {gy + 5}v2.2"/></g>')
    else:
        sv.add(f'<g><rect x="{gx + 1.2}" y="{gy + 4.4}" width="7.6" height="5.6" rx="1" fill="{color}"/>'
               f'<path d="M{gx + 2.9} {gy + 4.6}v-1.6a2.1 2.1 0 0 1 4.2 0v1.6" fill="none" stroke="{color}" '
               f'stroke-width="1.3"/></g>')


def pastilla_acceso(sv, clave, x, y, alto, rid, sobre):
    """Marcador PUBLICO / API KEY / PRIVADO con icono; (x, y) = esquina superior izquierda."""
    texto, fondo, color = ACCESO[clave]
    w = ancho_texto(texto, 12, True) + 30
    sv.rect(x, y, w, alto, rid, "pastilla", rx=alto / 2, relleno=fondo)
    glifo(sv, clave, x + 8, y + (alto - 10) / 2, color)
    sv.texto(x + 22, y + alto / 2 + 4.2, texto, 12, True, color, dueno=rid, rol="pastilla",
             extra=f' data-sobre="{sobre}"')
    return w


def pastilla(sv, texto, x, y, fondo, color, rid, sobre, alto=18):
    w = ancho_texto(texto, 12, True) + 16
    sv.rect(x, y, w, alto, rid, "pastilla", rx=alto / 2, relleno=fondo)
    sv.texto(x + 8, y + alto / 2 + 4.2, texto, 12, True, color, dueno=rid, rol="pastilla",
             extra=f' data-sobre="{sobre}"')
    return w


def grupo(sv, g):
    x, y, w, h, tipo = g["x"], g["y"], g["w"], g["h"], g["tipo"]
    if tipo in PESTANAS:
        fondo, borde, alto_tab, tam, r = PESTANAS[tipo]
        sv.rect(x, y, w, h, g["id"], "grupo", rx=r, relleno="none", borde=borde, grosor=1.6 if tipo == "aws" else 1.4)
        tw = ancho_texto(g["texto"], tam, True) + 22
        sv.add(f'<path d="M{x} {y + alto_tab}V{y + r}Q{x} {y} {x + r} {y}H{x + tw}V{y + alto_tab}Z" fill="{fondo}" '
               f'data-rect="{g["id"]}_tab" data-tipo="tab" data-x="{x}" data-y="{y}" data-w="{tw}" data-h="{alto_tab}"/>')
        sv.texto(x + 11, y + alto_tab / 2 + tam * 0.36, g["texto"], tam, True, "#FFFFFF", dueno=f'{g["id"]}_tab',
                 rol="grupo")
    elif tipo == "subred":
        sv.rect(x, y, w, h, g["id"], "grupo", rx=6, relleno="#F4F8EC", borde="#7AA116", grosor=1.2)
        sv.texto(x + 10, y + 18, g["texto"], 12, True, "#3F6212", dueno=g["id"], rol="grupo")
    elif tipo == "sg":
        sv.rect(x, y, w, h, g["id"], "grupo", rx=6, relleno="none", borde="#DD344C", grosor=1.2, guiones="5 4")
        if g.get("abajo"):
            n = len(g["abajo"])
            for i, t in enumerate(g["abajo"]):
                sv.texto(x + 10, y + h - 10 - 16 * (n - 1 - i), t, 12, i == 0, "#B91C32", dueno=g["id"], rol="grupo")
        else:
            sv.texto(x + 10, y + 17, g["texto"], 12, False, "#B91C32", dueno=g["id"], rol="grupo")
    elif tipo == "contenedor":
        sv.rect(x, y, w, h, g["id"], "grupo", rx=8, relleno="#FFF8F1", borde="#ED7100", grosor=1.2)
        pastilla(sv, g["texto"], x + 10, y - 9, COLOR_CONTENEDOR, "#FFFFFF", f'{g["id"]}_tag', g["id"])


def caja(sv, c):
    nombre, fondo_tag, borde = CATEGORIAS[c["cat"]]
    x, y, w, h, cid = c["x"], c["y"], c["w"], c["h"], c["id"]
    sv.rect(x, y, w, h, cid, "caja", rx=8 if nombre else 6, relleno="#FFFFFF", borde=borde,
            grosor=1.5 if nombre else 1.2)
    if nombre:
        pastilla(sv, nombre, x + 10, y - 9, fondo_tag, "#FFFFFF", f"{cid}_cat", cid)
    if c.get("acceso"):
        texto = ACCESO[c["acceso"]][0]
        pw = ancho_texto(texto, 12, True) + 30
        py = y + h - 9 if c.get("pos") == "abajo" else y - 9
        pastilla_acceso(sv, c["acceso"], x + w - 10 - pw, py, 18, f"{cid}_acceso", cid)
    tam = c.get("tam", 14)
    titulos = c["titulo"] if isinstance(c["titulo"], list) else [c["titulo"]]
    base = y + (28 if nombre else 22)
    for i, t in enumerate(titulos):
        sv.texto(x + 10, base + i * (tam + 3), t, tam, True, TINTA, dueno=cid, rol="titulo")
    base += (len(titulos) - 1) * (tam + 3)
    for i, item in enumerate(map(linea, c["lineas"])):
        con_pastilla = bool(item.get("acceso") or item.get("pro"))
        base += (20 if con_pastilla else 18) if i == 0 else (19 if con_pastilla else 16)
        tx = x + 10 + item.get("sangria", 0)
        if item.get("pro"):
            texto, fondo, color = PRO
            tx += pastilla(sv, texto, tx, base - 12, fondo, color, f"{cid}_pro{i}", cid, alto=16) + 6
        sv.texto(tx, base, item["t"], 12, item.get("b", False), TEXTO, item.get("mono", False), dueno=cid, rol="linea")
        if item.get("t2"):
            sv.texto(x + 10 + item["x2"], base, item["t2"], 12, False, TEXTO, item.get("mono", False), dueno=cid,
                     rol="linea")
        if item.get("acceso"):
            pw = ancho_texto(ACCESO[item["acceso"]][0], 12, True) + 30
            pastilla_acceso(sv, item["acceso"], x + w - 10 - pw, base - 12, 16, f"{cid}_acc{i}", cid)


def ruta(puntos, r=6):
    """Polilinea con esquinas redondeadas."""
    d = f"M{puntos[0][0]:g} {puntos[0][1]:g}"
    for (x0, y0), (x1, y1), (x2, y2) in zip(puntos, puntos[1:], puntos[2:]):
        l1, l2 = abs(x1 - x0) + abs(y1 - y0), abs(x2 - x1) + abs(y2 - y1)
        k1, k2 = min(r, l1 / 2) / l1, min(r, l2 / 2) / l2
        d += (f"L{x1 - (x1 - x0) * k1:g} {y1 - (y1 - y0) * k1:g}"
              f"Q{x1:g} {y1:g} {x1 + (x2 - x1) * k2:g} {y1 + (y2 - y1) * k2:g}")
    return d + f"L{puntos[-1][0]:g} {puntos[-1][1]:g}"


TAM_PUNTA = {"datos": 10, "clave": 12, "control": 9}


def flecha(sv, f):
    color, grosor, guiones = LINEAS[f["tipo"]]
    pts = [tuple(p) for p in f["puntos"]]
    # se recorta el final para que la punta (no el trazo grueso) toque el borde destino
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    largo = abs(xb - xa) + abs(yb - ya)
    corte = min(TAM_PUNTA[f["tipo"]] / 2, largo / 2)
    pts[-1] = (xb - (xb - xa) / largo * corte, yb - (yb - ya) / largo * corte)
    attrs = f'fill="none" stroke="{color}" stroke-width="{grosor}" stroke-linejoin="round"'
    if guiones:
        attrs += f' stroke-dasharray="{guiones}"'
    datos = " ".join(f"{x:g},{y:g}" for x, y in f["puntos"])
    sv.add(f'<path d="{ruta(pts)}" {attrs} marker-end="url(#punta-{f["tipo"]})" data-flecha="{f["id"]}" '
           f'data-pts="{datos}" data-de="{f["de"]}" data-a="{f["a"]}"/>')


def numero(sv, n, cx, cy, rid):
    sv.add(f'<circle cx="{cx}" cy="{cy}" r="10" fill="#232F3E" stroke="#FFFFFF" stroke-width="1.5" '
           f'data-num="{rid}" data-x="{cx - 10}" data-y="{cy - 10}"/>')
    sv.texto(cx, cy + 4.2, str(n), 12, True, "#FFFFFF", ancla="middle", dueno=f"num:{rid}", rol="numero")


def etiqueta(sv, f):
    lineas_, x, y, ancla = f["etiqueta"]
    for i, t in enumerate(lineas_):
        sv.texto(x, y + 16 * i, t, 12, False, TEXTO, ancla=ancla, rol="etiqueta", halo=True,
                 extra=f' data-flecha="{f["id"]}"')


def muestra_linea(sv, tipo, x, y, largo=36):
    color, grosor, guiones = LINEAS[tipo]
    corte = TAM_PUNTA[tipo] / 2
    attrs = f'stroke="{color}" stroke-width="{grosor}"' + (f' stroke-dasharray="{guiones}"' if guiones else "")
    sv.add(f'<path d="M{x} {y}H{x + largo - corte}" {attrs} marker-end="url(#punta-{tipo})" data-flecha="ley_{tipo}" '
           f'data-pts="{x},{y} {x + largo},{y}"/>')


def leyendas(sv):
    lx, ly = LEYENDA["x"], LEYENDA["y"]
    sv.rect(lx, ly, LEYENDA["w"], LEYENDA["h"], "leyenda", "leyenda", rx=8, relleno="#F7F8FA", borde="#D5DBDB")
    sv.texto(lx + 12, ly + 21, "Líneas", 12, True, TINTA, dueno="leyenda", rol="leyenda")
    x = lx + 70
    for tipo, texto in (("datos", "flujo de datos"), ("clave", "requiere x-api-key"), ("control", "control / despliegue")):
        muestra_linea(sv, tipo, x, ly + 17)
        sv.texto(x + 42, ly + 21, texto, 12, False, TEXTO, dueno="leyenda", rol="leyenda")
        x += 42 + ancho_texto(texto) + 26
    numero(sv, "n", x + 10, ly + 17, "leyenda")
    sv.texto(x + 26, ly + 21, "n.º de flujo (abajo)", 12, False, TEXTO, dueno="leyenda", rol="leyenda")
    sv.texto(lx + 12, ly + 47, "Acceso", 12, True, TINTA, dueno="leyenda", rol="leyenda")
    x = lx + 70
    for clave, texto in (("publico", "sin key"), ("clave", "header x-api-key"),
                         ("privado", "sin acceso directo desde Internet")):
        w = pastilla_acceso(sv, clave, x, ly + 34, 18, f"ley_{clave}", "leyenda")
        sv.texto(x + w + 6, ly + 47, texto, 12, False, TEXTO, dueno="leyenda", rol="leyenda")
        x += w + 6 + ancho_texto(texto) + 26
    texto, fondo, color = PRO
    w = pastilla(sv, texto, x, ly + 34, fondo, color, "ley_pro", "leyenda")
    sv.texto(x + w + 6, ly + 47, "nivel PRO", 12, False, TEXTO, dueno="leyenda", rol="leyenda")

    fx, fy = CAJA_FLUJOS["x"], CAJA_FLUJOS["y"]
    sv.rect(fx, fy, CAJA_FLUJOS["w"], CAJA_FLUJOS["h"], "flujos", "leyenda", rx=8, relleno="#F7F8FA",
            borde="#D5DBDB")
    for i, (n, texto) in enumerate(FLUJOS):
        col, fila = divmod(i, 4)
        x, cy = fx + 14 + col * 780, fy + 20 + fila * 20
        numero(sv, n, x + 10, cy, f"flujo{n}")
        sv.texto(x + 26, cy + 4.2, texto, 12, False, TEXTO, dueno="flujos", rol="leyenda")
    sv.texto(fx + 14, fy + 102, NOTA, 12, False, SUAVE, dueno="flujos", rol="leyenda")


def a_svg():
    sv = Lienzo()
    sv.add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}" '
           f'font-family="{FUENTE}" role="img" aria-labelledby="titulo-svg desc-svg">')
    sv.add('<title id="titulo-svg">Arquitectura de Escape de Manta Zombie en AWS</title>')
    sv.add('<desc id="desc-svg">Navegador, jurado y operador entran por CloudFront (HTTPS). CloudFront sirve el '
           'frontend desde S3 y envía /paso, /estado, /salud y /ws* a un ALB, que reenvía a una sola tarea de ECS '
           'en Fargate con la API FastAPI, el simulador, el mundo y el planner en memoria. La tarea guarda snapshots '
           'en DynamoDB, lee la API key de SSM Parameter Store, descarga la imagen de ECR y envía logs a CloudWatch.'
           '</desc>')
    sv.add("<defs>")
    for tipo, (color, _, _) in LINEAS.items():
        t = TAM_PUNTA[tipo]
        sv.add(f'<marker id="punta-{tipo}" viewBox="0 0 10 10" refX="5" refY="5" markerUnits="userSpaceOnUse" '
               f'markerWidth="{t}" markerHeight="{t}" orient="auto"><path d="M0 0L10 5L0 10z" fill="{color}"/></marker>')
    sv.add("</defs>")
    sv.rect(0, 0, ANCHO, ALTO, rx=0, relleno="#FFFFFF")
    sv.texto(24, 42, TITULO, 24, True, TINTA, rol="titulo-lienzo")
    sv.texto(24, 64, SUBTITULO, 13, False, SUAVE, rol="titulo-lienzo")
    leyendas(sv)
    # de afuera hacia adentro: el mas grande primero
    piezas = [("g", g) for g in GRUPOS] + [("c", c) for c in CAJAS]
    for clase, e in sorted(piezas, key=lambda p: -p[1]["w"] * p[1]["h"]):
        (grupo if clase == "g" else caja)(sv, e)
    for f in FLECHAS:
        flecha(sv, f)
    for f in FLECHAS:
        if f.get("etiqueta"):
            etiqueta(sv, f)
        if f.get("num"):
            numero(sv, *f["num"], f["id"])
    sv.add("</svg>")
    return "\n".join(sv.partes) + "\n"


if __name__ == "__main__":
    salida = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "docs" / "arquitectura.svg")
    salida.write_text(a_svg(), encoding="utf-8")
    print(f"escrito {salida}")
