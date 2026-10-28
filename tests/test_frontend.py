"""El mapa en vivo (frontend/) es index.html + css/ + js/, sin compilar. Estos tests cuidan que
index.html enlace solo archivos que existen, que no vuelva a tener codigo en linea (la CSP no lo
permite) y que los scripts, que comparten el ambito global, no declaren dos veces el mismo nombre."""
import os
import re
from html.parser import HTMLParser

FRONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


class _Index(HTMLParser):
    def __init__(self):
        super().__init__()
        self.locales, self.scripts, self.en_linea, self.estilos, self.csp = [], [], 0, 0, ""
        self._script = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        ruta = a.get("src") if tag == "script" else a.get("href") if tag == "link" else None
        if ruta and not re.match(r"(https?:|data:|//)", ruta):
            self.locales.append(ruta)
            if tag == "script":
                self.scripts.append(ruta)
        self._script = tag == "script" and not a.get("src")
        self.estilos += tag == "style"
        if tag == "meta" and (a.get("http-equiv") or "").lower() == "content-security-policy":
            self.csp = a.get("content") or ""

    def handle_data(self, data):
        self.en_linea += self._script and bool(data.strip())

    def handle_endtag(self, tag):
        self._script = False


def _index():
    p = _Index()
    p.feed(open(os.path.join(FRONT, "index.html"), encoding="utf-8").read())
    return p


def test_index_enlaza_solo_archivos_que_existen():
    locales = _index().locales
    assert "css/estilos.css" in locales and "js/main.js" in locales
    assert [r for r in locales if not os.path.isfile(os.path.join(FRONT, r))] == []


def test_index_sin_codigo_en_linea_y_con_csp_estricta():
    p = _index()
    assert p.en_linea == 0 and p.estilos == 0
    script_src = re.search(r"script-src([^;]*)", p.csp).group(1)
    assert "'unsafe-inline'" not in script_src and "'unsafe-eval'" not in script_src


def test_todo_css_y_js_esta_enlazado_y_main_va_al_final():
    p = _index()
    for carpeta in ("css", "js"):
        for f in os.listdir(os.path.join(FRONT, carpeta)):
            assert f"{carpeta}/{f}" in p.locales, f"{carpeta}/{f} no esta enlazado en index.html"
    assert p.scripts[-1] == "js/main.js"


def test_scripts_estrictos_y_sin_nombres_globales_repetidos():
    # Un const o una function repetidos entre dos scripts clasicos es un SyntaxError que apaga ese
    # archivo entero (y el mapa con el). Solo mira declaraciones en la columna 0, que son las globales.
    vistos = {}
    for src in _index().scripts:
        texto = open(os.path.join(FRONT, src), encoding="utf-8").read()
        assert texto.startswith("'use strict';"), src
        for nombre in re.findall(r"^(?:async\s+)?(?:function\s*\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)", texto, re.M):
            assert nombre not in vistos, f"{nombre} se declara en {vistos[nombre]} y en {src}"
            vistos[nombre] = src
    assert len(vistos) > 50
