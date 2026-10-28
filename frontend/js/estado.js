'use strict';
// Recibe cada estado del mundo y lo reparte entre el panel (hud.js) y el mapa (capas.js).

// ================= Estado recibido =================
let ultimo = null, tTurno = 0, primerEstado = true;

function recibir(e) {
  if (!e || typeof e !== 'object' || Array.isArray(e) || e.ping) return;
  const previo = ultimo;
  const turno = esNum(e.turno) ? e.turno : 0;
  const turnoNuevo = !previo || turno !== previo.turno;
  if (turnoNuevo) tTurno = Date.now();
  // Ronda nueva o repetida: sus eventos (mismo turno y calle) se vuelven a avisar
  if (previo && (e.ronda !== previo.ronda || turno < (esNum(previo.turno) ? previo.turno : 0))) eventosVistos.clear();
  ultimo = e;
  try { pintarHUD(e, turnoNuevo); } catch (err) { console.error('HUD', err); }
  try { if (G.listo) recibirMapa(e, previo); } catch (err) { console.error('mapa', err); }
  primerEstado = false;
}

function recibirMapa(e, previo) {
  const prevTurno = previo && esNum(previo.turno) ? previo.turno : 0;
  const reinicio = previo && (e.ronda !== previo.ronda || (esNum(e.turno) ? e.turno : 0) < prevTurno);
  if (reinicio) reiniciarActores();
  const animar = !!previo && !reinicio && !document.hidden;
  const mordidos = esNum(objeto(e.metricas).mordidos) ? e.metricas.mordidos : 0;
  const mordidosAntes = previo && esNum(objeto(previo.metricas).mordidos) ? previo.metricas.mordidos : mordidos;
  pintarBloqueadas(e.aristasBloqueadas, e, !previo);
  pintarZonas(e);
  pintarRefugiosMapa(datosRefugios(e));
  pintarZombies(lista(e.zombies), animar);
  pintarSobrevivientes(lista(e.sobrevivientes), animar, Math.max(0, mordidos - mordidosAntes));
  pintarCamionetas(lista(e.camionetas), animar);
  if (!Array.isArray(e.eventos)) pintarEventos(eventosLocales);
  if (animados.size) arrancarAnimacion();
}

function restantes(e) {
  if (!e) return null;
  if (esNum(e.turnosRestantes)) return e.turnosRestantes;
  const m = objeto(e.metricas);
  return esNum(m.turnosRestantes) ? m.turnosRestantes : null;
}
function corriendoAhora() {
  if (!ultimo) return false;
  if (typeof ultimo.corriendo === 'boolean') return ultimo.corriendo;
  // Backend antiguo sin "corriendo": se deduce de que el turno siga avanzando
  return esNum(ultimo.turno) && ultimo.turno > 0 && Date.now() - tTurno < 3 * TURNO_MS + 1000;
}
