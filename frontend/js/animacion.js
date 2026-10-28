'use strict';
// Animacion de los actores entre turnos, siempre por las calles del grafo.

// ================= Animacion =================
// Cada actor guarda su posicion dibujada (pos) y un camino de puntos que recorre en ANIM_MS desde t0.
const animados = new Set();
let rafId = 0;

function crearActor(capa, grupo, nodo, tooltip) {
  const act = {capa, grupo, nodo, pos: G.nodos.get(nodo), pts: null, acum: null, total: 0};
  capa.bindTooltip(() => tooltip(act), {direction: 'top', offset: [0, capa instanceof L.CircleMarker ? -6 : -16]});
  grupo.addLayer(capa);
  return act;
}

function programar(act, pts) {
  const acum = [0];
  let total = 0;
  for (let i = 1; i < pts.length; i++) { total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); acum.push(total); }
  if (total < 1e-9) { animados.delete(act); return; }
  Object.assign(act, {pts, acum, total, t0: performance.now()});
  animados.add(act);
}

function ubicar(act, k) {
  const d = k * act.total, acum = act.acum;
  let i = 1;
  while (i < acum.length - 1 && acum[i] < d) i++;
  const a = act.pts[i - 1], b = act.pts[i], tramo = acum[i] - acum[i - 1];
  const f = tramo > 0 ? Math.min(1, Math.max(0, (d - acum[i - 1]) / tramo)) : 1;
  act.pos = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  act.capa.setLatLng(act.pos);
}

// Salta sin animar (actor nuevo, pestana oculta o movimiento imposible por calles)
function saltar(act, nodo) {
  act.nodo = nodo; act.pos = G.nodos.get(nodo); animados.delete(act);
  act.capa.setLatLng(act.pos);
}

// Mueve un actor por una lista de nodos que empieza en su nodo actual
function mover(act, camino, nodoNuevo, animar) {
  // Ya va hacia ese nodo: el backend publica dos veces por turno (zombies y luego personas) y no
  // hay que reiniciar la animacion (cortaria la esquina en diagonal)
  if (animar && nodoNuevo === act.nodo && animados.has(act)) return;
  if (!animar || !camino) { saltar(act, nodoNuevo); return; }
  act.nodo = nodoNuevo;
  programar(act, [act.pos, ...camino.map(n => G.nodos.get(n))]);
}

const suave = t => t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;

function cuadro(ahora) {
  rafId = 0;
  if (!enZoom) {
    for (const act of animados) {
      const t = Math.min(1, Math.max(0, (ahora - act.t0) / ANIM_MS));
      ubicar(act, suave(t));
      if (t >= 1) animados.delete(act);
    }
  }
  if (animados.size) rafId = requestAnimationFrame(cuadro);
}

function arrancarAnimacion() {
  if (!rafId && animados.size) rafId = requestAnimationFrame(cuadro);
}

// Une el nodo actual con los nodos recorridos este turno; null si no hay camino por calles
function unir(desde, nodos) {
  nodos = nodos.filter(n => G.nodos.has(n));
  if (!nodos.length) return null;
  if (nodos[0] === desde) return nodos;
  const i = nodos.indexOf(desde);
  if (i > 0) return nodos.slice(i);
  if (adyacentes(desde, nodos[0])) return [desde, ...nodos];
  for (const v of G.vecinos.get(desde) || []) if (adyacentes(v, nodos[0])) return [desde, v, ...nodos];
  return null;
}
