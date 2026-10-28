'use strict';
// Control del operador: botones que llaman a /ws/sim/* con la key de operador.

// ================= Control del operador =================
const botonesOp = [...document.querySelectorAll('[data-accion]')];
function salidaOp(texto, tono) { const el = $('op-salida'); el.textContent = texto; el.dataset.tono = tono || ''; }

async function operar(boton) {
  const clave = $('api-key').value.trim();
  if (!clave) { salidaOp('Escribe primero la key de operador (ADMIN_API_KEY).', 'error'); $('api-key').focus(); return; }
  const {accion, ronda} = boton.dataset;
  if (accion === 'detener' && !confirm('¿Detener la ronda en curso?')) return;
  const metodo = accion === 'resultados' ? 'GET' : 'POST';
  const url = '/ws/sim/' + accion + (accion === 'iniciar' ? '?ronda=' + encodeURIComponent(ronda) : '');
  botonesOp.forEach(b => { b.disabled = true; });
  salidaOp(`${metodo} ${url} …`);
  const ctl = new AbortController(), corte = setTimeout(() => ctl.abort(), 15000);
  try {
    const r = await fetch(url, {method: metodo, headers: {'x-api-key': clave}, cache: 'no-store', signal: ctl.signal});
    const cuerpo = await r.text();
    let bonito = cuerpo;
    try {
      const d = JSON.parse(cuerpo);
      bonito = JSON.stringify(d, null, 2);
      if (r.ok && accion === 'resultados') pintarResultados(d.resultados);
    } catch { /* respuesta que no es JSON: se muestra tal cual */ }
    salidaOp(`HTTP ${r.status}${r.statusText ? ' ' + r.statusText : ''}\n${bonito}`, r.ok ? 'ok' : 'error');
    if (r.ok && accion !== 'resultados') pedirEstado();
  } catch (err) {
    salidaOp(`Sin respuesta del servidor (${err.name === 'AbortError' ? 'tiempo agotado' : err.message}).`, 'error');
  } finally {
    clearTimeout(corte);
    botonesOp.forEach(b => { b.disabled = false; });
  }
}
botonesOp.forEach(b => b.addEventListener('click', () => operar(b)));
