'use strict';
// Conexion con el servidor: WebSocket /ws y, si falla, polling a /estado.

// ================= Conexion: WebSocket con respaldo de polling =================
// ws: socket actual (uno a la vez); wsVivo: ya trajo al menos un estado. Hay a lo sumo un intervalo
// de polling, un reintento agendado y un socket; los sockets abandonados se sueltan sin esperar su close.
let ws = null, wsVivo = false, wsReintento = 0, wsIntento = 0, wsPausa = WS_REINTENTO_MS, ultimoMensaje = 0;
let pollTimer = 0, pidiendo = false, fallosPoll = 0, pideClave = false;

function setConexion(modo) {
  const el = $('conexion');
  if (el.dataset.modo === modo) return;
  el.dataset.modo = modo;
  const [txt, det, titulo] = {
    ws: ['En vivo', ' · WebSocket', 'Recibe cada turno al instante por WebSocket'],
    polling: ['Polling', ' · cada 2 s', 'El WebSocket no está disponible: se consulta /estado cada 2 segundos'],
    sin: ['Sin conexión', ' · reintentando', 'No hay respuesta del servidor; se sigue reintentando'],
    clave: ['Sin acceso', ' · falta la key', 'El servidor pide una key para leer el estado: escríbela en Control del operador'],
  }[modo] || ['Conectando…', '', ''];
  poner($('con-txt'), txt); poner($('con-det'), det); el.title = titulo;
}
function conectarWS() {
  wsReintento = 0;
  if (ws) return;
  wsIntento = Date.now(); ultimoMensaje = 0; wsVivo = false;
  try { ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws'); }
  catch (err) { soltarWS(); return; }
  const sock = ws;
  sock.onmessage = ev => {
    ultimoMensaje = Date.now();
    let d;
    try { d = JSON.parse(ev.data); } catch { return; }
    if (!d || typeof d !== 'object' || d.ping) return;  // los {"ping":true} solo mantienen viva la conexion
    if (!wsVivo) { wsVivo = true; detenerPolling(); setConexion('ws'); }  // el polling sigue hasta el primer estado
    recibir(d);
  };
  sock.onclose = () => { if (ws === sock) soltarWS(); };  // un error siempre termina en close: basta este evento
}

// Suelta el socket sin esperar su evento close (con la red caida el navegador tarda hasta un minuto
// en darlo), sigue por polling y agenda otro intento. Si el socket duro poco, cada intento espera el doble.
function soltarWS() {
  const sock = ws, duro = wsVivo && Date.now() - wsIntento > 30000;
  ws = null; wsVivo = false;
  if (sock) {
    sock.onmessage = sock.onclose = null;
    try { sock.close(); } catch { /* ya estaba cerrado */ }
  }
  iniciarPolling();
  if (duro) wsPausa = WS_REINTENTO_MS;
  programarWS();
  if (!duro) wsPausa = Math.min(WS_REINTENTO_MAX_MS, wsPausa * 2);
}
// El proximo intento se cuenta desde que empezo el anterior
function programarWS() {
  if (!wsReintento) wsReintento = setTimeout(conectarWS, Math.max(1000, wsPausa - (Date.now() - wsIntento)));
}

function iniciarPolling() {
  if (pollTimer) return;
  if ($('conexion').dataset.modo === 'ws' || $('conexion').dataset.modo === 'conectando') setConexion('polling');
  pedirEstado();
  pollTimer = setInterval(pedirEstado, POLL_MS);
}
function detenerPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = 0; } }

async function pedirEstado() {
  if (pidiendo) return;
  pidiendo = true;
  const pedidoEn = Date.now();
  const ctl = new AbortController(), corte = setTimeout(() => ctl.abort(), 4000);
  try {
    const clave = $('api-key').value.trim();
    const r = await fetch('/estado', {cache: 'no-store', signal: ctl.signal, headers: pideClave && clave ? {'x-api-key': clave} : {}});
    if (r.status === 401 || r.status === 403) { pideClave = true; if (pollTimer && !wsVivo) setConexion('clave'); return; }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    fallosPoll = 0;
    if (wsVivo && ultimoMensaje >= pedidoEn) return;  // el WebSocket ya trajo un estado igual o mas nuevo
    if (pollTimer && !wsVivo) setConexion('polling');
    recibir(d);
  } catch (err) {
    if (++fallosPoll >= 2 && pollTimer && !wsVivo) setConexion('sin');
  } finally {
    clearTimeout(corte);
    pidiendo = false;
  }
}

// Vigia: un socket que no abre, o que abrio y quedo mudo (sin estado ni ping), se suelta y se sigue
// por polling. En ronda llega un estado por turno: 10 s de silencio ya es una conexion muerta.
setInterval(() => {
  if (!ws) return;
  const limite = ws.readyState === WebSocket.CONNECTING ? WS_ESPERA_MS
    : !wsVivo || (ultimo && ultimo.corriendo === true) ? WS_SILENCIO_RONDA_MS : WS_SILENCIO_MS;
  if (Date.now() - Math.max(ultimoMensaje, wsIntento) > limite) soltarWS();
}, 1000);
window.addEventListener('online', () => { if (!ws) { clearTimeout(wsReintento); wsPausa = WS_REINTENTO_MS; conectarWS(); } });
