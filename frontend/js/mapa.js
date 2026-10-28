'use strict';
// Mapa base de Leaflet y grafo de calles (manta_graph.json).

// ================= Mapa base =================
const HAY_MAPA = typeof window.L !== 'undefined';
let mapa = null, rCalles, rZonas, rRutas, rBloqueos, rActores, capaCalles, capaZonas, capaRutas, capaRutasCam, capaActores, capaMarcas, capaEtiquetas;
let enZoom = false;

if (HAY_MAPA) {
  mapa = L.map('mapa', {preferCanvas: true, zoomSnap: .5, minZoom: 11, maxZoom: 19}).setView([-0.955, -80.72], 14);
  mapa.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores de OpenStreetMap</a>',
  }).addTo(mapa);
  // Un canvas por capa: animar a los sobrevivientes no obliga a redibujar las 500 calles
  const lienzo = (nombre, z, extra) => { mapa.createPane(nombre).style.zIndex = z; return L.canvas({pane: nombre, padding: .3, ...extra}); };
  rCalles = lienzo('calles', 410);
  rZonas = lienzo('zonas', 420);
  rRutas = lienzo('rutas', 430);
  rBloqueos = lienzo('bloqueos', 435);
  rActores = lienzo('actores', 440, {tolerance: 4, padding: .1});  // se redibuja en cada cuadro: lienzo chico
  mapa.createPane('etiquetas').style.zIndex = 450;
  [capaCalles, capaZonas, capaRutas, capaRutasCam, capaActores, capaMarcas, capaEtiquetas] = Array.from({length: 7}, () => L.layerGroup().addTo(mapa));
  mapa.on('zoomstart', () => { enZoom = true; });
  mapa.on('zoomend', () => { enZoom = false; ajustarEscala(); });
  movil.addEventListener('change', ajustarEscala);

  // Boton para volver a ver toda la ciudad
  const Encuadre = L.Control.extend({
    options: {position: 'topleft'},
    onAdd() {
      const caja = L.DomUtil.create('div', 'leaflet-bar');
      const b = L.DomUtil.create('button', 'btn-encuadre', caja);
      b.type = 'button'; b.title = 'Ver toda la ciudad'; b.setAttribute('aria-label', 'Ver toda la ciudad'); b.textContent = '⤢';
      L.DomEvent.disableClickPropagation(caja);
      L.DomEvent.on(b, 'click', encuadrar);
      return caja;
    },
  });
  new Encuadre().addTo(mapa);
} else {
  mostrarError('No se pudo cargar la librería del mapa (Leaflet). Los datos de la simulación siguen actualizándose en el panel.');
}

// ================= Grafo =================
const G = {
  nodos: new Map(),       // id -> [lat, lng]
  vecinos: new Map(),     // id -> Set(ids)
  calles: new Map(),      // id -> calle del grafo
  lineas: new Map(),      // id calle -> polyline
  refugios: [],           // refugios del grafo
  refugioNodo: new Map(), // nodo -> id refugio
  limites: null, radioZona: 40, listo: false,
};
const ordenRefugios = [];

function registrarRefugios(ids) {
  for (const id of [...ids].map(String).sort(cmpIds)) if (!ordenRefugios.includes(id)) ordenRefugios.push(id);
}
function colorRefugio(id) {
  if (id == null) return COLOR_SIN_REFUGIO;
  if (!ordenRefugios.includes(String(id))) ordenRefugios.push(String(id));
  return COLORES_REFUGIO[ordenRefugios.indexOf(String(id))] || COLOR_SIN_REFUGIO;
}
const estiloCalle = tipo => ({...(ESTILO_CALLE[tipo] || ESTILO_CALLE.calle), dashArray: null});
const adyacentes = (a, b) => !!(G.vecinos.get(a) && G.vecinos.get(a).has(b));

async function cargarGrafo() {
  if (!HAY_MAPA) return;
  try {
    const r = await fetch('manta_graph.json', {cache: 'no-cache'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    construirGrafo(await r.json());
    mostrarError('');
  } catch (err) {
    mostrarError(`No se pudo cargar el mapa de la ciudad (manta_graph.json: ${err.message}). Reintentando en 10 s…`);
    setTimeout(cargarGrafo, 10000);
  }
}

function construirGrafo(g) {
  const nodos = lista(g && g.nodos).filter(n => n && n.id != null && esNum(n.lat) && esNum(n.lng));
  if (!nodos.length) throw new Error('el archivo no tiene nodos');
  for (const n of nodos) { G.nodos.set(String(n.id), [n.lat, n.lng]); G.vecinos.set(String(n.id), new Set()); }
  const largos = [];
  for (const c of lista(g.calles)) {
    if (!c || c.id == null) continue;
    const de = String(c.de), a = String(c.a), pa = G.nodos.get(de), pb = G.nodos.get(a);
    if (!pa || !pb) continue;
    G.vecinos.get(de).add(a); G.vecinos.get(a).add(de);
    G.calles.set(String(c.id), c);
    if (esNum(c.distancia_m) && c.distancia_m > 0) largos.push(c.distancia_m);
    const linea = L.polyline([pa, pb], {...estiloCalle(c.tipo), renderer: rCalles, interactive: false});
    G.lineas.set(String(c.id), linea);
    capaCalles.addLayer(linea);
  }
  // Radio de las zonas de horda segun el largo tipico de una calle
  largos.sort((x, y) => x - y);
  if (largos.length) G.radioZona = Math.min(90, Math.max(25, largos[largos.length >> 1] * .35));
  G.refugios = lista(g.refugios).filter(r => r && r.id != null && G.nodos.has(String(r.nodo)));
  registrarRefugios(G.refugios.map(r => r.id));
  for (const r of G.refugios) G.refugioNodo.set(String(r.nodo), String(r.id));
  for (const b of lista(g.barrios)) {
    if (!b || !esNum(b.lat) || !esNum(b.lng)) continue;
    L.marker([b.lat, b.lng], {pane: 'etiquetas', interactive: false, keyboard: false,
      icon: L.divIcon({className: 'mk-barrio', iconSize: [0, 0], html: `<div class="barrio">${esc(b.nombre || b.id)}</div>`})}).addTo(capaEtiquetas);
  }
  G.limites = L.latLngBounds([...G.nodos.values()]);
  encuadrar();
  ajustarEscala();
  mapa.setMinZoom(Math.max(11, Math.floor(mapa.getZoom()) - 2));
  mapa.setMaxBounds(G.limites.pad(.6));
  G.listo = true;
  if (ultimo) { recibirMapa(ultimo, null); }
}

// Encuadra la ciudad; si sobra alto, la sube para que la leyenda abierta no tape calles
function encuadrar() {
  if (!mapa || !G.limites) return;
  const z = mapa.getBoundsZoom(G.limites, false, L.point(48, 48));
  const alto = Math.abs(mapa.project(G.limites.getSouthWest(), z).y - mapa.project(G.limites.getNorthEast(), z).y);
  const ley = $('leyenda').dataset.abierta === 'true' && !movil.matches ? $('leyenda').offsetHeight : 0;
  const extra = Math.max(0, Math.min(ley, mapa.getSize().y - 48 - alto - 1));
  mapa.fitBounds(G.limites, {paddingTopLeft: [24, 24], paddingBottomRight: [24, 24 + extra]});
}

// Con la ciudad entera en una pantalla chica los iconos se achican y las etiquetas de refugio
// se ocultan (tocar un refugio muestra su nombre y ocupacion)
function ajustarEscala() {
  if (!mapa) return;
  const z = mapa.getZoom();
  $('mapa').classList.toggle('compacto', movil.matches ? z < 14.5 : z < 12.5);
}
