"""Diagrama de arquitectura de Escape de Manta Zombie: modelo unico + exportacion a draw.io.

El modelo (grupos, cajas, flechas y numeros de flujo, con coordenadas puestas a mano en un
lienzo de 1600x1000) lo usan este script, que escribe arquitectura.drawio (XML sin comprimir,
se abre en diagrams.net), y gen_svg.py, que dibuja arquitectura.svg. Asi ambos quedan iguales.

Uso: python gen_drawio.py [salida.drawio]
"""
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ANCHO, ALTO = 1600, 1000
FUENTE = "Arial, Helvetica, 'Liberation Sans', system-ui, sans-serif"
FUENTE_MONO = "Consolas, 'Courier New', monospace"

# Categorias tipo iconos AWS: (nombre en la etiqueta, color de la etiqueta, color del borde)
CATEGORIAS = {
    "internet": ("Internet", "#545B64", "#545B64"),
    "equipo": ("Equipo", "#545B64", "#545B64"),
    "redes": ("Redes", "#7B3FE4", "#8C4FFF"),
    "contenedores": ("Contenedores", "#C8511B", "#ED7100"),
    "almacenamiento": ("Almacenamiento", "#3F8624", "#7AA116"),
    "basedatos": ("Base de datos", "#A1189E", "#C925D1"),
    "gestion": ("Gestión", "#C7105E", "#E7157B"),
    "seguridad": ("Seguridad", "#C7131F", "#DD344C"),
    "finanzas": ("Finanzas", "#3F8624", "#7AA116"),
    "pieza": (None, None, "#7D8998"),  # componentes dentro del contenedor
}

# Marcadores de acceso: (texto, relleno, color del texto)
ACCESO = {
    "publico": ("PÚBLICO", "#1D8102", "#FFFFFF"),
    "clave": ("API KEY", "#FBBF24", "#1F2937"),
    "operador": ("KEY OPERADOR", "#F59E0B", "#1F2937"),
    "privado": ("PRIVADO", "#414D5C", "#FFFFFF"),
}
PRO = ("PRO", "#0F766E", "#FFFFFF")

# Pestanas de los grupos AWS y VPC: (relleno, borde del grupo, alto, tamano de letra, radio)
PESTANAS = {"aws": ("#232F3E", "#232F3E", 24, 13, 10), "vpc": ("#7B3FE4", "#8C4FFF", 22, 12, 8)}
COLOR_CONTENEDOR = "#C8511B"  # pastilla con el nombre del contenedor

# Estilos de linea: (color, grosor, patron de guiones)
LINEAS = {
    "datos": ("#232F3E", 1.8, None),
    "clave": ("#D97706", 2.6, None),
    "control": ("#5F6B7A", 1.5, "6 4"),
}

TITULO = "Escape de Manta Zombie · Arquitectura en AWS"
SUBTITULO = "Spookython 2026 · Track A · rutas recalculadas cada turno (2 s) alrededor de zombies y calles cerradas"

# ---------------------------------------------------------------- grupos (fronteras)
# tipo: aws | vpc | subred | sg | contenedor. 'abajo': etiqueta al pie (lista de lineas).
GRUPOS = [
    dict(id="aws", x=254, y=84, w=1324, h=782, tipo="aws",
         texto="AWS us-east-1 · una sola cuenta del equipo"),
    dict(id="vpc", x=518, y=112, w=836, h=578, tipo="vpc", texto="VPC por defecto"),
    dict(id="subred", x=530, y=142, w=812, h=538, tipo="subred",
         texto="Subredes públicas (2 AZ) · sin NAT Gateway"),
    dict(id="sg_alb", x=542, y=236, w=172, h=310, tipo="sg",
         abajo=["SG manta-sg-alb:", ":80 solo desde el prefix", "list de CloudFront"]),
    dict(id="sg_tarea", x=740, y=170, w=590, h=500, tipo="sg",
         texto="SG manta-sg-tarea · :8000 solo desde manta-sg-alb"),
    dict(id="contenedor", x=762, y=286, w=546, h=364, tipo="contenedor",
         texto="Contenedor api · uvicorn con 1 worker en :8000 · usuario no root"),
]

# ---------------------------------------------------------------- cajas
# lineas: texto, o dict(t, b=negrita, mono, acceso=<marcador a la derecha>, pro=<pastilla PRO>,
#         sangria=px, t2=segunda columna, x2=posicion de t2)
# acceso/pos: marcador de la caja ('arriba' o 'abajo', a la derecha). tam: tamano del titulo.
CAJAS = [
    # --- personas (fuera de AWS)
    dict(id="nav", x=20, y=112, w=186, h=108, cat="internet", titulo="Navegador",
         lineas=["mapa en vivo (Leaflet)", "GET /, css/, js/ y el grafo", "WS /ws o GET /estado c/2 s",
                 "sin API key"]),
    dict(id="jurado", x=20, y=238, w=186, h=88, cat="internet", titulo="Jurado / simulador",
         lineas=["POST /paso + x-api-key", "respuesta en < 500 ms", "pruebas de latencia (p95)"]),
    dict(id="operador", x=20, y=344, w=186, h=88, cat="internet", titulo="Operador del equipo",
         lineas=["panel «Control» del mapa", "/ws/sim/* + key de operador", "iniciar · detener · reanudar"]),
    dict(id="equipo", x=20, y=700, w=186, h=120, cat="equipo", titulo="Despliegue (equipo)",
         lineas=["usuarios IAM propios + MFA", "./infra/deploy.sh (AWS CLI)", "access key solo durante",
                 "el evento"]),
    # --- borde de AWS
    dict(id="cf", x=270, y=120, w=196, h=284, cat="redes", acceso="publico", titulo="Amazon CloudFront",
         lineas=["HTTPS · servicio global", "d160b5kavxovby.cloudfront.net", "plan Free (tarifa plana)",
                 dict(t="5 behaviors (máx. del plan):", b=True),
                 dict(t="/paso", t2="→ ALB", x2=78, mono=True),
                 dict(t="/estado", t2="→ ALB", x2=78, mono=True),
                 dict(t="/salud", t2="→ ALB", x2=78, mono=True),
                 dict(t="/ws*", t2="→ ALB", x2=78, mono=True),
                 dict(t="Default", t2="→ S3", x2=78, mono=True)]),
    dict(id="waf", x=282, y=328, w=172, h=64, cat="seguridad", tam=13, titulo="AWS WAF (incluido)",
         lineas=["puede dar 403 en ráfagas"]),
    dict(id="s3", x=270, y=436, w=196, h=112, cat="almacenamiento", acceso="privado", pos="abajo",
         titulo="Amazon S3",
         lineas=["bucket frontend-manta", "index.html, css/, js/ y el grafo", "solo vía CloudFront (OAC)"]),
    # --- VPC
    dict(id="alb", x=552, y=250, w=152, h=220, cat="redes", acceso="privado", pos="abajo",
         titulo=["Application", "Load Balancer"],
         lineas=["manta-alb · HTTP :80", "target group manta-tg", "destino IP :8000", "health check /salud"]),
    dict(id="tarea", x=750, y=204, w=570, h=456, cat="contenedores", acceso="privado",
         titulo="Amazon ECS en AWS Fargate",
         lineas=["cluster manta · servicio manta-api · 1 sola tarea (el estado del juego vive en memoria)",
                 "ARM64 (Graviton) · 0.5 vCPU · 1 GB · IP pública, sin NAT Gateway"]),
    dict(id="api", x=774, y=306, w=234, h=140, cat="pieza", tam=13, titulo="API FastAPI",
         lineas=[dict(t="POST /paso", mono=True, acceso="clave"),
                 dict(t="/ws/sim/*", mono=True, acceso="operador"),
                 dict(t="GET /estado", mono=True, acceso="publico"),
                 dict(t="WS /ws", mono=True, acceso="publico"),
                 dict(t="GET /salud", mono=True, acceso="publico")]),
    dict(id="sim", x=1062, y=306, w=234, h=140, cat="pieza", tam=13, titulo="Simulador del Apocalipsis",
         lineas=["cada 2 s, en este orden:", "eventos (puente o avenida cae)", "→ se mueven los zombies",
                 "→ publica el Mundo", "→ sobrevivientes piden /paso", "→ mordidas, refugios y camionetas"]),
    dict(id="planner", x=774, y=490, w=306, h=148, cat="pieza", tam=13, titulo="Planner de rutas",
         lineas=["1 Dijkstra inverso por refugio, 1 vez por turno",
                 "costo = segundos por tipo de calle + riesgo",
                 "nodos con zombie y zonas de horda: prohibidos",
                 "POST /paso solo consulta estas tablas",
                 dict(t="predicción de corredores", pro=True),
                 dict(t="capacidad de refugios · flota de 5 camionetas", sangria=38)]),
    dict(id="mundo", x=1120, y=490, w=176, h=148, cat="pieza", tam=13, titulo="Mundo",
         lineas=["estado publicado inmutable", "turno, zombies, zonas de", "horda, calles bloqueadas,",
                 "sobrevivientes, camionetas,", "cupos de refugios, métricas", "en memoria de la tarea"]),
    # --- columna derecha
    dict(id="iam", x=1384, y=112, w=180, h=206, cat="seguridad", titulo="AWS IAM",
         lineas=["usuarios individuales + MFA", "(root solo creó los 2 roles)", dict(t="grupo MantaTeam", b=True),
                 "9 políticas administradas,", "sin AdministratorAccess", "PassRole solo a 2 roles",
                 dict(t="manta-execution-role", b=True), "ECR, logs y /manta/* (SSM)",
                 dict(t="manta-task-role", b=True), "DynamoDB manta-snapshots"]),
    dict(id="ddb", x=1384, y=356, w=180, h=196, cat="basedatos", acceso="privado", pos="abajo",
         titulo="Amazon DynamoDB",
         lineas=["tabla manta-snapshots", "on-demand · TTL 7 días", "snapshot cada 10 turnos",
                 "+ resultado de cada ronda", "/ws/sim/reanudar lee el", "último snapshot",
                 "vía manta-task-role:", "PutItem/GetItem/Query"]),
    dict(id="budgets", x=1384, y=720, w=180, h=132, cat="finanzas", titulo="AWS Budgets",
         lineas=["manta-zombie-mensual", "50 USD/mes · alertas", "50/80/100 % + pronóstico",
                 "a 3 correos del equipo", "(avisa, no corta el gasto)"]),
    # --- fila inferior
    dict(id="ecr", x=600, y=720, w=196, h=132, cat="contenedores", acceso="privado", pos="abajo",
         titulo="Amazon ECR",
         lineas=["repositorio manta-zombie", "imagen ARM64 (:latest, :sha)", "la tarea la descarga con",
                 "manta-execution-role"]),
    dict(id="ssm", x=820, y=720, w=214, h=132, cat="gestion", acceso="privado", pos="abajo",
         titulo="AWS Systems Manager",
         lineas=["Parameter Store (SecureString)", "/manta/api-key → API_KEY", "/manta/admin-key (operador)",
                 "(manta-execution-role)"]),
    dict(id="cw", x=1054, y=720, w=300, h=132, cat="gestion", acceso="privado", titulo="Amazon CloudWatch",
         lineas=["Logs /ecs/manta-zombie · retención 7 días", "filtros de métricas sobre los logs:",
                 "p95 de /paso, errores, mordidos y", "salvados por ronda · alarmas (opcional)"]),
]

# ---------------------------------------------------------------- flechas
# puntos: polilinea absoluta (el primero sobre el borde de 'de', el ultimo sobre el de 'a').
# num: (n, x, y) circulo con el numero de flujo. etiqueta: (lineas, x, y_base, ancla).
FLECHAS = [
    dict(id="f_nav1", de="nav", a="cf", tipo="datos", puntos=[(206, 148), (270, 148)], num=(1, 230, 148)),
    dict(id="f_nav2", de="nav", a="cf", tipo="datos", puntos=[(206, 188), (270, 188)], num=(2, 230, 188)),
    dict(id="f_jurado", de="jurado", a="cf", tipo="clave", puntos=[(206, 282), (270, 282)], num=(3, 230, 282)),
    dict(id="f_operador", de="operador", a="cf", tipo="clave", puntos=[(206, 388), (270, 388)]),
    dict(id="f_cf_s3", de="cf", a="s3", tipo="datos", puntos=[(432, 404), (432, 436)], num=(1, 450, 420)),
    dict(id="f_cf_alb3", de="cf", a="alb", tipo="clave", puntos=[(466, 350), (552, 350)], num=(3, 492, 350)),
    dict(id="f_cf_alb2", de="cf", a="alb", tipo="datos", puntos=[(466, 388), (552, 388)], num=(2, 492, 388)),
    dict(id="f_alb_api3", de="alb", a="api", tipo="clave", puntos=[(704, 350), (774, 350)]),
    dict(id="f_alb_api2", de="alb", a="api", tipo="datos", puntos=[(704, 388), (774, 388)]),
    # dentro del contenedor
    dict(id="f_sim_api", de="sim", a="api", tipo="clave", puntos=[(1062, 350), (1008, 350)], num=(4, 1035, 350)),
    dict(id="f_api_plan", de="api", a="planner", tipo="datos", puntos=[(830, 446), (830, 490)], num=(3, 830, 467)),
    dict(id="f_api_mundo", de="api", a="mundo", tipo="datos",
         puntos=[(980, 446), (980, 468), (1150, 468), (1150, 490)], num=(2, 1065, 468)),
    dict(id="f_sim_mundo", de="sim", a="mundo", tipo="datos", puntos=[(1240, 446), (1240, 490)], num=(4, 1240, 467)),
    dict(id="f_mundo_plan", de="mundo", a="planner", tipo="datos", puntos=[(1120, 566), (1080, 566)],
         num=(4, 1100, 548)),
    # hacia servicios de datos
    dict(id="f_sim_ddb", de="sim", a="ddb", tipo="datos", puntos=[(1296, 400), (1384, 400)], num=(5, 1369, 384)),
    dict(id="f_tarea_cw", de="tarea", a="cw", tipo="datos", puntos=[(1200, 660), (1200, 720)], num=(6, 1216, 705)),
    dict(id="f_ecr_tarea", de="ecr", a="tarea", tipo="control", puntos=[(780, 720), (780, 660)], num=(7, 764, 705)),
    dict(id="f_ssm_tarea", de="ssm", a="tarea", tipo="control", puntos=[(930, 720), (930, 660)]),
    # despliegue
    dict(id="f_deploy", de="equipo", a="ecr", tipo="control", puntos=[(206, 792), (600, 792)], num=(7, 230, 792),
         etiqueta=(["docker buildx (ARM64) --push → ecs update-service"], 268, 782, "start")),
    dict(id="f_s3sync", de="equipo", a="s3", tipo="control", puntos=[(206, 730), (320, 730), (320, 548)],
         num=(7, 230, 730), etiqueta=(["s3 sync + invalidación", "de CloudFront"], 330, 640, "start")),
]

# ---------------------------------------------------------------- leyendas
LEYENDA = dict(x=700, y=10, w=878, h=62)
FLUJOS = [
    (1, "Página y grafo: Navegador → CloudFront → S3 (index.html, css/, js/ y manta_graph.json, con OAC)."),
    (2, "Estado en vivo: WS /ws (o GET /estado cada 2 s) → CloudFront → ALB → API, que lee el Mundo publicado."),
    (3, "POST /paso con x-api-key → CloudFront → ALB → ruta ASGI directa → consulta las tablas del planner (< 500 ms)."),
    (4, "Turno de 2 s: el simulador aplica eventos y mueve zombies → publica el Mundo → el planner recalcula 1 vez → /paso."),
    (5, "Snapshot cada 10 turnos y resultado de cada ronda → DynamoDB (manta-task-role)."),
    (6, "Logs JSON del contenedor → CloudWatch Logs; filtros de métricas y alarmas opcionales (p95, errores, mordidos)."),
    (7, "Despliegue: docker buildx ARM64 → ECR → ecs update-service; frontend: s3 sync + invalidación de CloudFront."),
]
NOTA = ("Notas: el ALB es internet-facing, pero su SG solo admite el prefix list de CloudFront (header x-origin-verify "
        "listo, sin activar) · WebSocket por CloudFront Free probado (si falla, polling de /estado) · "
        "/estado y /ws son públicos por PUBLIC_STATE=true.")
CAJA_FLUJOS = dict(x=20, y=878, w=1558, h=114)

# ---------------------------------------------------------------- medidas de texto
# Anchos de Arial/Helvetica en milesimas de em (texto normal y negrita); los acentos miden
# igual que su letra base. Sirve para dimensionar pastillas y etiquetas; el chequeo final
# (verificar.py) mide el texto real en el navegador.
_NORMAL = dict(zip(" !\"#$%&'()*+,-./0123456789:;<=>?@", [278, 278, 355, 556, 556, 889, 667, 191, 333, 333,
               389, 584, 278, 333, 278, 278] + [556] * 10 + [278, 278, 584, 584, 584, 556, 1015]))
_NORMAL.update(dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556,
                    833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611])))
_NORMAL.update(dict(zip("abcdefghijklmnopqrstuvwxyz", [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222,
                    833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500])))
_NORMAL.update({"[": 278, "]": 278, "_": 556, "|": 260, "·": 278, "«": 556, "»": 556, "→": 1000, "÷": 584,
                "×": 584, "–": 556, "—": 1000, "º": 365})
_NEGRITA = dict(_NORMAL)
_NEGRITA.update(dict(zip("abcdefghijklmnopqrstuvwxyz", [556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278,
                     889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500])))
_NEGRITA.update({"A": 722, "B": 722, "J": 556, "K": 722, "L": 611, ":": 333, "!": 333, "?": 611, "(": 333,
                 ")": 333})
_BASE = str.maketrans("áéíóúÁÉÍÓÚñÑü", "aeiouAEIOUnNu")


def ancho_texto(texto, tam=12, negrita=False, mono=False):
    """Ancho aproximado en px (mono: 0.61 em, el peor caso entre Consolas/Menlo/DejaVu)."""
    if mono:
        return len(texto) * 0.61 * tam
    tabla = _NEGRITA if negrita else _NORMAL
    return sum(tabla.get(c, 556) for c in texto.translate(_BASE)) * tam / 1000


# ---------------------------------------------------------------- utilidades del modelo
def elementos():
    """Grupos y cajas con su padre (el elemento mas chico que lo contiene) para draw.io."""
    todos = [dict(g, clase="grupo") for g in GRUPOS] + [dict(c, clase="caja") for c in CAJAS]

    def contiene(a, b):
        return (a is not b and a["x"] <= b["x"] and a["y"] <= b["y"]
                and a["x"] + a["w"] >= b["x"] + b["w"] and a["y"] + a["h"] >= b["y"] + b["h"])

    for e in todos:
        padres = [p for p in todos if contiene(p, e)]
        e["padre"] = min(padres, key=lambda p: p["w"] * p["h"])["id"] if padres else None
    return {e["id"]: e for e in todos}


def ancestros(elems, eid):
    cadena = []
    while eid:
        cadena.append(eid)
        eid = elems[eid]["padre"]
    return cadena


def linea(item):
    return item if isinstance(item, dict) else {"t": item}


def proyectar(puntos, px, py):
    """Distancia a lo largo de la polilinea del punto mas cercano a (px, py) y ese punto."""
    mejor, recorrido = None, 0.0
    for (x0, y0), (x1, y1) in zip(puntos, puntos[1:]):
        largo = math.hypot(x1 - x0, y1 - y0)
        f = 0.0 if largo == 0 else max(0.0, min(1.0, ((px - x0) * (x1 - x0) + (py - y0) * (y1 - y0)) / largo ** 2))
        qx, qy = x0 + f * (x1 - x0), y0 + f * (y1 - y0)
        d = math.hypot(px - qx, py - qy)
        if mejor is None or d < mejor[0]:
            mejor = (d, recorrido + f * largo, qx, qy)
        recorrido += largo
    return mejor[1], mejor[2], mejor[3], recorrido


# ---------------------------------------------------------------- exportacion a draw.io
def _esc(texto):
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pastilla_html(texto, fondo, color):
    return (f'<span style="background-color:{fondo};color:{color};font-weight:bold;">'
            f'&nbsp;{_esc(texto)}&nbsp;</span>')


def _html_caja(c):
    titulos = c["titulo"] if isinstance(c["titulo"], list) else [c["titulo"]]
    partes = [f'<b><font style="font-size:{c.get("tam", 14)}px" color="#16191F">'
              + "<br>".join(_esc(t) for t in titulos) + "</font></b>"]
    for item in map(linea, c["lineas"]):
        txt = _esc(item["t"] + (" " + item["t2"] if item.get("t2") else ""))
        if item.get("mono"):
            txt = f'<font face="Courier New">{txt}</font>'
        if item.get("b"):
            txt = f"<b>{txt}</b>"
        if item.get("pro"):
            txt = _pastilla_html(*PRO) + " " + txt
        if item.get("sangria"):
            txt = "&nbsp;" * 9 + txt
        if item.get("acceso"):
            txt += " " + _pastilla_html(*ACCESO[item["acceso"]])
        partes.append(txt)
    return "<br>".join(partes)


ESTILO_GRUPO = {
    "aws": "fillColor=none;strokeColor=#232F3E;strokeWidth=1.6;fontColor=#232F3E;fontStyle=1;fontSize=13;",
    "vpc": "fillColor=none;strokeColor=#8C4FFF;strokeWidth=1.4;fontColor=#7B3FE4;fontStyle=1;fontSize=12;",
    "subred": "fillColor=#F4F8EC;strokeColor=#7AA116;strokeWidth=1.2;fontColor=#3F6212;fontStyle=1;fontSize=12;",
    "sg": "fillColor=none;strokeColor=#DD344C;strokeWidth=1.2;dashed=1;dashPattern=5 4;fontColor=#B91C32;fontSize=12;",
    "contenedor": "fillColor=#FFF8F1;strokeColor=#ED7100;strokeWidth=1.2;fontColor=#C8511B;fontStyle=1;fontSize=12;",
}


def a_drawio():
    elems = elementos()
    abs_ = {i: (e["x"], e["y"]) for i, e in elems.items()}
    raiz = ET.Element("root")
    ET.SubElement(raiz, "mxCell", id="0")
    ET.SubElement(raiz, "mxCell", id="1", parent="0")

    def celda(cid, valor, estilo, x, y, w, h, padre=None, vertice=True):
        ox, oy = abs_[padre] if padre else (0, 0)
        attrs = dict(id=cid, value=valor, style=estilo, parent=padre or "1")
        attrs["vertex" if vertice else "edge"] = "1"
        c = ET.SubElement(raiz, "mxCell", attrs)
        ET.SubElement(c, "mxGeometry", x=f"{x - ox:g}", y=f"{y - oy:g}", width=f"{w:g}", height=f"{h:g}",
                      **{"as": "geometry"})
        return c

    def pastilla(cid, texto, fondo, color, x, y, padre):
        w = ancho_texto(texto, 12, True) + 16
        celda(cid, texto, f"rounded=1;arcSize=50;html=1;whiteSpace=nowrap;fillColor={fondo};strokeColor=none;"
                          f"fontColor={color};fontStyle=1;fontSize=12;", x, y, w, 18, padre)
        return w

    texto_libre = "text;html=1;align=left;verticalAlign=middle;whiteSpace=nowrap;fontSize=12;fontColor=#333D47;"
    celda("titulo", f"<b>{_esc(TITULO)}</b>", texto_libre + "fontSize=24;fontColor=#16191F;", 24, 18, 620, 30)
    celda("subtitulo", _esc(SUBTITULO), texto_libre + "fontSize=13;fontColor=#545B64;", 24, 50, 760, 20)

    # grupos y cajas, de afuera hacia adentro (draw.io necesita el padre antes que los hijos)
    for e in sorted(elems.values(), key=lambda e: len(ancestros(elems, e["id"]))):
        comun = "rounded=1;html=1;whiteSpace=wrap;"
        if e["clase"] == "grupo":
            vertical = "verticalAlign=bottom;spacingBottom=4;" if e.get("abajo") else "verticalAlign=top;spacingTop=2;"
            valor = "<br>".join(_esc(t) for t in e["abajo"]) if e.get("abajo") else _esc(e["texto"])
            if e["tipo"] in PESTANAS or e["tipo"] == "contenedor":
                valor = ""  # el nombre va en una pestana o pastilla propia, como en el SVG
            celda(e["id"], valor, comun + "arcSize=2;align=left;spacingLeft=10;container=1;collapsible=0;"
                  "recursiveResize=0;" + vertical + ESTILO_GRUPO[e["tipo"]], e["x"], e["y"], e["w"], e["h"], e["padre"])
            if e["tipo"] in PESTANAS:
                fondo, _, alto, tam, _ = PESTANAS[e["tipo"]]
                celda(f"{e['id']}_tab", f"<b>{_esc(e['texto'])}</b>", "rounded=0;html=1;whiteSpace=nowrap;align=left;"
                      f"spacingLeft=11;fillColor={fondo};strokeColor=none;fontColor=#FFFFFF;fontSize={tam};",
                      e["x"], e["y"], ancho_texto(e["texto"], tam, True) + 22, alto, e["id"])
            elif e["tipo"] == "contenedor":
                pastilla(f"{e['id']}_tag", e["texto"], COLOR_CONTENEDOR, "#FFFFFF", e["x"] + 10, e["y"] - 9, e["id"])
            continue
        nombre, fondo_tag, borde = CATEGORIAS[e["cat"]]
        contenedora = any(o["padre"] == e["id"] for o in elems.values())
        celda(e["id"], _html_caja(e), comun + f"arcSize={4 if e['w'] > 300 else 6};align=left;verticalAlign=top;"
              f"spacingLeft=10;spacingTop={14 if nombre else 4};fillColor=#FFFFFF;strokeColor={borde};"
              f"strokeWidth={1.5 if nombre else 1.2};fontSize=12;fontColor=#333D47;"
              + ("container=1;collapsible=0;recursiveResize=0;" if contenedora else ""),
              e["x"], e["y"], e["w"], e["h"], e["padre"])
        if nombre:
            pastilla(f"{e['id']}_cat", nombre, fondo_tag, "#FFFFFF", e["x"] + 10, e["y"] - 9, e["id"])
        if e.get("acceso"):
            texto, fondo, color = ACCESO[e["acceso"]]
            w = ancho_texto(texto, 12, True) + 16
            y = e["y"] + e["h"] - 9 if e.get("pos") == "abajo" else e["y"] - 9
            pastilla(f"{e['id']}_acceso", texto, fondo, color, e["x"] + e["w"] - 10 - w, y, e["id"])

    # flechas: padre = ancestro comun, puntos de salida/entrada fijos y etiqueta en su lugar
    for f in FLECHAS:
        color, grosor, guiones = LINEAS[f["tipo"]]
        cadena_a = ancestros(elems, f["a"])
        padre = next((p for p in ancestros(elems, f["de"])[1:] if p in cadena_a[1:]), None)
        (x0, y0), (x1, y1) = f["puntos"][0], f["puntos"][-1]
        o, d = elems[f["de"]], elems[f["a"]]
        estilo = (f"html=1;rounded=1;edgeStyle=none;endArrow=block;endFill=1;endSize=7;strokeColor={color};"
                  f"strokeWidth={grosor};fontSize=12;fontColor=#333D47;labelBackgroundColor=#FFFFFF;"
                  f"exitX={(x0 - o['x']) / o['w']:.4f};exitY={(y0 - o['y']) / o['h']:.4f};exitPerimeter=0;"
                  f"entryX={(x1 - d['x']) / d['w']:.4f};entryY={(y1 - d['y']) / d['h']:.4f};entryPerimeter=0;"
                  + (f"dashed=1;dashPattern={guiones};" if guiones else ""))
        valor = "<br>".join(_esc(t) for t in f["etiqueta"][0]) if f.get("etiqueta") else ""
        ox, oy = abs_[padre] if padre else (0, 0)
        c = ET.SubElement(raiz, "mxCell", id=f["id"], value=valor, style=estilo, parent=padre or "1",
                          source=f["de"], target=f["a"], edge="1")
        geo = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        if f.get("etiqueta"):
            lineas_, lx, ly, ancla = f["etiqueta"]
            w = max(ancho_texto(t) for t in lineas_)
            cx = lx + {"start": w / 2, "middle": 0, "end": -w / 2}[ancla]
            cy = ly - 4 + 8 * (len(lineas_) - 1)
            s, qx, qy, largo = proyectar(f["puntos"], cx, cy)
            geo.set("x", f"{2 * s / largo - 1:.4f}")
            ET.SubElement(geo, "mxPoint", x=f"{cx - qx:g}", y=f"{cy - qy:g}", **{"as": "offset"})
        if len(f["puntos"]) > 2:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for px, py in f["puntos"][1:-1]:
                ET.SubElement(arr, "mxPoint", x=f"{px - ox:g}", y=f"{py - oy:g}")

    # numeros de flujo
    def numero(cid, n, cx, cy):
        padres = [e for e in elems.values() if e["x"] <= cx - 10 and cx + 10 <= e["x"] + e["w"]
                  and e["y"] <= cy - 10 and cy + 10 <= e["y"] + e["h"]]
        padre = min(padres, key=lambda e: e["w"] * e["h"])["id"] if padres else None
        celda(cid, str(n), "ellipse;html=1;fillColor=#232F3E;strokeColor=#FFFFFF;strokeWidth=1.5;fontColor=#FFFFFF;"
              "fontStyle=1;fontSize=12;", cx - 10, cy - 10, 20, 20, padre)

    for f in FLECHAS:
        if f.get("num"):
            numero(f"{f['id']}_num", *f["num"])

    # leyenda de lineas y acceso (arriba a la derecha)
    lx, ly = LEYENDA["x"], LEYENDA["y"]
    celda("leyenda", "", "rounded=1;arcSize=8;html=1;fillColor=#F7F8FA;strokeColor=#D5DBDB;",
          lx, ly, LEYENDA["w"], LEYENDA["h"])
    celda("ley_lineas", "<b>Líneas</b>", texto_libre, lx + 12, ly + 6, 50, 20)
    x = lx + 70
    for tipo, texto in (("datos", "flujo de datos"), ("clave", "requiere x-api-key"), ("control", "control / despliegue")):
        color, grosor, guiones = LINEAS[tipo]
        c = ET.SubElement(raiz, "mxCell", id=f"ley_linea_{tipo}", value="", parent="1", edge="1",
                          style=f"html=1;endArrow=block;endFill=1;endSize=7;strokeColor={color};strokeWidth={grosor};"
                          + (f"dashed=1;dashPattern={guiones};" if guiones else ""))
        geo = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(geo, "mxPoint", x=f"{x}", y=f"{ly + 16}", **{"as": "sourcePoint"})
        ET.SubElement(geo, "mxPoint", x=f"{x + 36}", y=f"{ly + 16}", **{"as": "targetPoint"})
        celda(f"ley_linea_{tipo}_t", _esc(texto), texto_libre, x + 42, ly + 6, ancho_texto(texto) + 8, 20)
        x += 42 + ancho_texto(texto) + 26
    numero("ley_num", "n", x + 10, ly + 16)
    celda("ley_num_t", "n.º de flujo (abajo)", texto_libre, x + 26, ly + 6, 120, 20)
    celda("ley_acceso", "<b>Acceso</b>", texto_libre, lx + 12, ly + 32, 56, 20)
    x = lx + 70
    for clave, texto in (("publico", "sin key"), ("clave", "header x-api-key"),
                         ("privado", "sin acceso directo desde Internet")):
        w = pastilla(f"ley_acceso_{clave}_p", *ACCESO[clave], x, ly + 33, None)
        celda(f"ley_acceso_{clave}_t", _esc(texto), texto_libre, x + w + 6, ly + 32, ancho_texto(texto) + 8, 20)
        x += w + 6 + ancho_texto(texto) + 26
    texto, fondo, color = PRO
    w = pastilla("ley_pro_p", texto, fondo, color, x, ly + 33, None)
    celda("ley_pro_t", "nivel PRO", texto_libre, x + w + 6, ly + 32, 70, 20)

    # flujos numerados (abajo)
    fx, fy = CAJA_FLUJOS["x"], CAJA_FLUJOS["y"]
    celda("flujos", "", "rounded=1;arcSize=6;html=1;fillColor=#F7F8FA;strokeColor=#D5DBDB;",
          fx, fy, CAJA_FLUJOS["w"], CAJA_FLUJOS["h"])
    for i, (n, texto) in enumerate(FLUJOS):
        col, fila = divmod(i, 4)
        x, y = fx + 14 + col * 780, fy + 20 + fila * 20
        numero(f"flujo{n}", n, x + 10, y)
        celda(f"flujo{n}_t", _esc(texto), texto_libre, x + 26, y - 10, 740, 20)
    celda("nota", _esc(NOTA), texto_libre + "fontColor=#545B64;", fx + 14, fy + 92, 1530, 20)

    ids = [c.get("id") for c in raiz]
    assert len(ids) == len(set(ids)), "ids repetidos en el XML de draw.io"

    modelo = ET.Element("mxGraphModel", dx="1600", dy="1000", grid="1", gridSize="10", guides="1", tooltips="1",
                        connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth=str(ANCHO),
                        pageHeight=str(ALTO), background="#FFFFFF", math="0", shadow="0")
    modelo.append(raiz)
    archivo = ET.Element("mxfile", host="app.diagrams.net", type="device")
    diagrama = ET.SubElement(archivo, "diagram", id="arquitectura-manta", name="Arquitectura")
    diagrama.append(modelo)
    ET.indent(archivo)
    return ET.tostring(archivo, encoding="unicode")


if __name__ == "__main__":
    salida = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "docs" / "arquitectura.drawio")
    salida.write_text(a_drawio(), encoding="utf-8")
    print(f"escrito {salida} ({len(GRUPOS)} grupos, {len(CAJAS)} cajas, {len(FLECHAS)} flechas)")
