'use strict';
// Lo que cambia cada turno en el mapa: zombies, sobrevivientes, camionetas,
// zonas de horda, calles bloqueadas y refugios.

// ================= Capas dinamicas =================
const zombies = new Map(), sobrevivientes = new Map(), camionetas = new Map();
const zonas = new Map(), halos = new Map(), bloqueadas = new Map(), refugios = new Map();
const iconosZombie = {};
let efectosActivos = 0;

// Se quita del grupo (no solo del mapa) para no dejar capas huerfanas dentro del LayerGroup
function quitarActor(act) {
  animados.delete(act);
  act.grupo.removeLayer(act.capa);
  if (act.linea) act.grupoLinea.removeLayer(act.linea);
}

function reiniciarActores() {
  for (const m of [zombies, sobrevivientes, camionetas]) { m.forEach(quitarActor); m.clear(); }
  eventosLocales.length = 0;
}

function claseZombie(z) {
  if (z.visible === false || z.tipo === 'dormido') return 'dormido';
  return ZOMBIE[z.tipo] ? z.tipo : 'caminante';
}
function iconoZombie(clase) {
  return iconosZombie[clase] || (iconosZombie[clase] = L.divIcon({
    className: 'mk-z mk-' + clase, iconSize: clase === 'horda' ? [40, 40] : [30, 30],
    html: `<div class="zb zb-${clase}">${ZOMBIE[clase].html}</div>`,
  }));
}
function textoZombie(act) {
  const z = act.datos || {};
  return `<b>${esc(ZOMBIE[act.clase].nombre)}</b> · ${esc(z.id)}` +
    (act.clase === 'dormido' ? '<br>Invisible para el motor hasta que despierte' : '') +
    (act.clase === 'horda' ? '<br>Bloquea su esquina y las vecinas' : '');
}

function pintarZombies(datos, animar) {
  const vistos = new Set();
  for (const z of datos) {
    if (!z || z.id == null || !G.nodos.has(String(z.nodo))) continue;
    const id = String(z.id), nodo = String(z.nodo), clase = claseZombie(z);
    vistos.add(id);
    let act = zombies.get(id);
    if (!act) {
      act = crearActor(L.marker(G.nodos.get(nodo), {icon: iconoZombie(clase), keyboard: false, zIndexOffset: 1000}), capaMarcas, nodo, textoZombie);
      act.clase = clase;
      zombies.set(id, act);
    } else {
      if (act.clase !== clase) { act.capa.setIcon(iconoZombie(clase)); act.clase = clase; }
      const pasos = lista(z.pasos).filter(p => Array.isArray(p) && p.length >= 2);
      const nodos = pasos.length ? [String(pasos[0][0]), ...pasos.map(p => String(p[1]))]
        : z.previo != null && String(z.previo) !== nodo ? [String(z.previo), nodo] : [nodo];
      mover(act, unir(act.nodo, nodos), nodo, animar);
    }
    act.datos = z;
  }
  for (const [id, act] of zombies) if (!vistos.has(id)) { quitarActor(act); zombies.delete(id); }
}

// Camino de una persona: un paso por calle o, si se salto un turno, por su ruta anterior
function caminoPersona(act, nodo) {
  if (nodo === act.nodo || adyacentes(act.nodo, nodo)) return [act.nodo, nodo];
  const i = (act.ruta || []).indexOf(nodo);
  return i > 0 && i <= 4 ? unir(act.nodo, act.ruta.slice(0, i + 1)) : unir(act.nodo, [nodo]);
}

function ponerRuta(act, ruta, grupo, estilo) {
  const firma = ruta.join(',') + estilo.color;
  if (act.firmaRuta === firma) return;
  act.firmaRuta = firma;
  if (ruta.length < 2) { if (act.linea) { grupo.removeLayer(act.linea); act.linea = null; } return; }
  const pts = ruta.map(n => G.nodos.get(n));
  if (!act.linea) {
    act.linea = L.polyline(pts, {...estilo, renderer: rRutas, interactive: false});
    act.grupoLinea = grupo;
    grupo.addLayer(act.linea);
  } else { act.linea.setLatLngs(pts); act.linea.setStyle(estilo); }
}

function refugioDeRuta(ruta) { return ruta.length ? G.refugioNodo.get(ruta[ruta.length - 1]) ?? null : null; }

function textoSobreviviente(act) {
  const s = act.datos || {}, r = refugios.get(act.ref);
  const destino = r ? (r.datos.nombre || r.id) : act.ref || 'sin refugio asignado';
  return `<b>${esc(s.id)}</b> → ${esc(destino)}` +
    (s.estado === 'esperando' ? '<br>Esperando camioneta' : '') +
    (s.estado === 'en_puerta' ? '<br>Espera en la puerta: el refugio está lleno' : '') +
    (act.ruta && act.ruta.length > 1 ? `<br>Ruta planificada: ${act.ruta.length - 1} calles` : '');
}

function pintarSobrevivientes(datos, animar, mordidosNuevos) {
  const vistos = new Set();
  for (const s of datos) {
    if (!s || s.id == null || !G.nodos.has(String(s.nodo))) continue;
    const id = String(s.id), nodo = String(s.nodo);
    vistos.add(id);
    const ruta = lista(s.ruta).map(String).filter(n => G.nodos.has(n));
    let act = sobrevivientes.get(id);
    const ref = s.refugio != null ? String(s.refugio) : refugioDeRuta(ruta) ?? (act ? act.ref : null);
    const color = colorRefugio(ref), espera = s.estado === 'esperando';
    if (!act) {
      act = crearActor(L.circleMarker(G.nodos.get(nodo), {renderer: rActores, radius: 5}), capaActores, nodo, textoSobreviviente);
      sobrevivientes.set(id, act);
    } else {
      mover(act, caminoPersona(act, nodo), nodo, animar);
    }
    const estilo = color + (espera ? '|e' : '');
    if (act.estilo !== estilo) {
      act.estilo = estilo;
      act.capa.setStyle(espera ? {radius: 6.5, color: '#f6ad55', weight: 2.5, fillColor: color, fillOpacity: 1}
        : {radius: 5, color: '#0b0b1a', weight: 1.5, fillColor: color, fillOpacity: 1});
    }
    ponerRuta(act, ruta, capaRutas, {color, weight: 2, opacity: .6});
    Object.assign(act, {datos: s, ruta, ref});
  }
  // Los que desaparecen: llegaron a un refugio, los mordieron o subieron a una camioneta
  const llegadas = new Map(), posibles = [];
  for (const [id, act] of sobrevivientes) {
    if (vistos.has(id)) continue;
    const refId = G.refugioNodo.get(act.nodo) || (act.ruta && G.refugioNodo.get(act.ruta[1]));
    if (refId) llegadas.set(refId, (llegadas.get(refId) || 0) + 1);
    else if (act.datos && act.datos.estado !== 'esperando') posibles.push(act.pos);
    quitarActor(act);
    sobrevivientes.delete(id);
  }
  if (!animar) return;
  for (const [refId, n] of llegadas) { const r = refugios.get(refId); if (r) efecto(G.nodos.get(r.nodo), `+${n} ✓`, 'fx-ok'); }
  posibles.slice(0, mordidosNuevos).forEach(pos => efecto(pos, '💀', 'fx-mal'));
}

function pintarCamionetas(datos, animar) {
  const vistos = new Set();
  for (const c of datos) {
    if (!c || c.id == null || !G.nodos.has(String(c.nodo))) continue;
    const id = String(c.id), nodo = String(c.nodo);
    vistos.add(id);
    let act = camionetas.get(id);
    if (!act) {
      act = crearActor(L.marker(G.nodos.get(nodo), {keyboard: false, zIndexOffset: 2000,
        icon: L.divIcon({className: 'mk-cam', iconSize: [30, 30], html: '<div class="cam">🚐<b>0</b></div>'})}), capaMarcas, nodo, textoCamioneta);
      camionetas.set(id, act);
    } else {
      mover(act, caminoPersona(act, nodo), nodo, animar);
    }
    const ruta = lista(c.ruta).map(String).filter(n => G.nodos.has(n));
    ponerRuta(act, ruta, capaRutasCam, {color: '#f6ad55', weight: 3, opacity: .9, dashArray: '2 7', lineCap: 'round'});
    Object.assign(act, {datos: c, ruta});
    const el = act.capa.getElement();
    if (el) {
      poner(el.querySelector('b'), esNum(c.pasajeros) ? c.pasajeros : '?');
      el.firstChild.classList.toggle('en-refugio', G.refugioNodo.has(nodo));  // no tapar el refugio
    }
  }
  for (const [id, act] of camionetas) if (!vistos.has(id)) { quitarActor(act); camionetas.delete(id); }
}
function textoCamioneta(act) {
  const c = act.datos || {};
  const estado = {recogiendo: 'va a recoger personas', entregando: 'lleva personas a un refugio', libre: 'libre'}[c.estado] || c.estado || '';
  return `<b>Camioneta ${esc(c.id)}</b><br>${esc(esNum(c.pasajeros) ? c.pasajeros : '?')} de ${esc(esNum(c.capacidad) ? c.capacidad : 4)} pasajeros` + (estado ? `<br>${esc(estado)}` : '');
}

function pintarZonas(e) {
  let nodos;
  if (Array.isArray(e.zonasHorda)) nodos = e.zonasHorda.map(String);
  else { // respaldo para backends antiguos: nodo de la horda + vecinos
    nodos = [];
    for (const z of lista(e.zombies)) if (z && z.tipo === 'horda' && G.nodos.has(String(z.nodo))) nodos.push(String(z.nodo), ...(G.vecinos.get(String(z.nodo)) || []));
  }
  const activos = new Set(nodos.filter(n => G.nodos.has(n)));
  for (const [n, c] of zonas) if (!activos.has(n)) { capaZonas.removeLayer(c); zonas.delete(n); }
  for (const n of activos) {
    if (zonas.has(n)) continue;
    const c = L.circle(G.nodos.get(n), {renderer: rZonas, radius: G.radioZona, color: '#ff5c5c', weight: 1, opacity: .7, fillColor: '#ff3b3b', fillOpacity: .3, interactive: false});
    capaZonas.addLayer(c);
    zonas.set(n, c);
  }
  pintarHalos(lista(e.zombies));
}

// Halo de peligro alrededor de cada horda: cubre su esquina y todas las vecinas
function pintarHalos(datos) {
  const vivas = new Set();
  for (const z of datos) {
    if (!z || z.tipo !== 'horda' || z.visible === false || !G.nodos.has(String(z.nodo))) continue;
    const id = String(z.id), nodo = String(z.nodo), centro = G.nodos.get(nodo);
    vivas.add(id);
    let h = halos.get(id);
    if (h && h.nodo === nodo) continue;
    let radio = G.radioZona * 2;
    for (const v of G.vecinos.get(nodo) || []) radio = Math.max(radio, mapa.distance(centro, G.nodos.get(v)) + G.radioZona);
    if (!h) {
      h = L.circle(centro, {renderer: rZonas, radius: radio, color: '#ff5c5c', weight: 1.5, opacity: .8, dashArray: '6 6', fillColor: '#ff3b3b', fillOpacity: .12, interactive: false});
      capaZonas.addLayer(h);
      halos.set(id, h);
    } else { h.setLatLng(centro); h.setRadius(radio); }
    h.nodo = nodo;
  }
  for (const [id, h] of halos) if (!vivas.has(id)) { capaZonas.removeLayer(h); halos.delete(id); }
}

// Alfiler sobre el punto medio de la calle: el cartel no tapa la calle cortada (si es corta)
const iconoBloqueo = () => L.divIcon({className: 'mk-bloq', iconSize: [24, 34], iconAnchor: [12, 34], html: '<div class="bloq">🚧</div>'});
const eventosLocales = [];

function pintarBloqueadas(ids, e, primera) {
  const activas = new Set(lista(ids).map(String).filter(id => G.calles.has(id)));
  for (const [id, m] of bloqueadas) {
    if (activas.has(id)) continue;
    capaMarcas.removeLayer(m); m.lineas.forEach(x => capaZonas.removeLayer(x)); bloqueadas.delete(id);
    const l = G.lineas.get(id); if (l) l.setStyle(estiloCalle(G.calles.get(id).tipo));
  }
  for (const id of activas) {
    if (bloqueadas.has(id)) continue;
    const c = G.calles.get(id);
    const a = G.nodos.get(String(c.de)), b = G.nodos.get(String(c.a));
    G.lineas.get(id).setStyle({opacity: .2});  // la calle sale del mapa vivo
    const lineas = [ESTILO_BLOQUEADA_FONDO, ESTILO_BLOQUEADA].map(est => L.polyline([a, b], {...est, renderer: rBloqueos, interactive: false}).addTo(capaZonas));
    const titulo = c.tipo === 'puente' ? 'Puente caído' : 'Calle bloqueada';
    const m = L.marker([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], {icon: iconoBloqueo(), keyboard: false, zIndexOffset: 1600})
      .bindTooltip(`<b>${titulo}</b>${c.nombre ? '<br>' + esc(c.nombre) : ''}<br><small>${esc(id)}</small>`, {direction: 'top', offset: [0, -36]})
      .addTo(capaMarcas);
    m.lineas = lineas;
    bloqueadas.set(id, m);
    // Backends sin "eventos": se arma el evento aqui. Si ya estaba bloqueada al abrir el mapa se
    // lista sin turno y sin aviso emergente
    if (!Array.isArray(e.eventos)) {
      const ev = {turno: primera ? null : e.turno, arista: id, texto: `${titulo}: ${c.nombre ? c.nombre + ' (' + id + ')' : id}`};
      if (primera) eventosVistos.add(claveEvento(ev));
      eventosLocales.push(ev);
      if (eventosLocales.length > 10) eventosLocales.shift();
    }
  }
}

function destacarArista(id) {
  const m = bloqueadas.get(String(id));
  const el = m && m.getElement();
  if (!el) return;
  const div = el.querySelector('.bloq');
  div.classList.remove('pulso-bloq'); void div.offsetWidth; div.classList.add('pulso-bloq');
}

function efecto(pos, texto, clase) {
  if (!pos || efectosActivos >= 40 || document.hidden) return;
  efectosActivos++;
  const m = L.marker(pos, {interactive: false, keyboard: false, zIndexOffset: 3000,
    icon: L.divIcon({className: 'mk-fx', iconSize: [60, 20], iconAnchor: [30, 26], html: `<div class="fx ${clase}">${esc(texto)}</div>`})}).addTo(capaMarcas);
  setTimeout(() => { capaMarcas.removeLayer(m); efectosActivos--; }, 1900);
}

// Refugios: union del grafo (nodo, nombre) y del estado (capacidad, ocupacion)
function datosRefugios(e) {
  const porId = new Map();
  for (const r of G.refugios) porId.set(String(r.id), {...r});
  for (const r of lista(e && e.refugios)) if (r && r.id != null) porId.set(String(r.id), {...porId.get(String(r.id)), ...r});
  // Personas esperando en la puerta de un refugio lleno (PRO capacidad)
  for (const s of lista(e && e.sobrevivientes)) {
    if (!s || s.estado !== 'en_puerta') continue;
    const r = porId.get(String(s.refugio ?? G.refugioNodo.get(String(s.nodo))));
    if (r) r.enPuerta = (r.enPuerta || 0) + 1;
  }
  return [...porId.values()].sort((a, b) => cmpIds(a.id, b.id));
}

function pintarRefugiosMapa(datos) {
  for (const d of datos) {
    const id = String(d.id), nodo = String(d.nodo);
    if (!G.nodos.has(nodo)) continue;
    let r = refugios.get(id);
    if (!r) {
      const color = colorRefugio(id);
      const icono = L.divIcon({className: 'mk-ref', iconSize: [34, 34],
        html: `<div class="ref" style="--c:${color}"><div class="ref-ico">🏠</div><div class="ref-info"><span class="ref-nom"></span><div class="ref-barra"><i></i></div><span class="ref-num"></span><span class="ref-puerta"></span><span class="ref-corto"></span></div></div>`});
      r = {id, nodo, marca: L.marker(G.nodos.get(nodo), {icon: icono, keyboard: false, zIndexOffset: 1800}).addTo(capaMarcas)};
      r.marca.bindTooltip(() => textoRefugio(r), {direction: 'bottom', offset: [0, 18]});
      refugios.set(id, r);
      G.refugioNodo.set(nodo, id);
    }
    r.datos = d;
    const el = r.marca.getElement();
    if (!el) continue;
    poner(el.querySelector('.ref-nom'), d.nombre || id);
    const info = el.querySelector('.ref-info'), barra = el.querySelector('.ref-barra'), num = el.querySelector('.ref-num');
    const puerta = el.querySelector('.ref-puerta'), corto = el.querySelector('.ref-corto');
    const cap = esNum(d.capacidad) && d.capacidad > 0 ? d.capacidad : null, oc = esNum(d.ocupacion) ? d.ocupacion : null;
    const sinDatos = cap == null || oc == null;
    info.classList.toggle('sin-datos', sinDatos);
    barra.hidden = num.hidden = corto.hidden = sinDatos;
    puerta.hidden = sinDatos || !d.enPuerta;
    if (sinDatos) continue;
    const f = Math.min(1, oc / cap), nivel = oc >= cap ? 'lleno' : f >= .8 ? 'alto' : 'ok';
    const cuenta = `${fmt0.format(oc)}/${fmt0.format(cap)}`;
    barra.dataset.nivel = info.dataset.nivel = nivel;
    barra.firstChild.style.width = (f * 100).toFixed(0) + '%';
    const html = cuenta + (nivel === 'lleno' ? ' · <b>LLENO</b>' : nivel === 'alto' ? ' personas · casi lleno' : ' personas');
    if (num.dataset.html !== html) { num.dataset.html = html; num.innerHTML = html; }
    if (d.enPuerta) poner(puerta, `${plural(d.enPuerta, 'espera', 'esperan')} en la puerta`);
    poner(corto, nivel === 'lleno' ? `${cuenta} lleno` : cuenta);
  }
}
function textoRefugio(r) {
  const d = r.datos || {};
  let t = `<b>${esc(d.nombre || r.id)}</b> (${esc(r.id)})`;
  if (esNum(d.capacidad) && esNum(d.ocupacion)) t += `<br>Ocupación: ${fmt0.format(d.ocupacion)} de ${fmt0.format(d.capacidad)}`;
  if (d.enPuerta) t += `<br>Esperan en la puerta: ${fmt0.format(d.enPuerta)}`;
  if (esNum(d.evacuaPorTurno)) t += `<br>Evacúa ${fmt0.format(d.evacuaPorTurno)} por turno`;
  return t;
}
