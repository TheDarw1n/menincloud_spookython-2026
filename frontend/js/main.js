'use strict';
/* Mapa en vivo de Escape de Manta Zombie.
   Datos: manta_graph.json (archivo estatico) + estado del mundo por WebSocket /ws, con respaldo
   de polling a /estado. Cualquier campo del estado puede faltar (backends antiguos): todo se lee
   de forma defensiva. Los marcadores se reutilizan por id y se animan entre turnos.
   Los archivos de js/ son scripts clasicos que comparten el ambito global y se cargan en el orden
   de index.html: cada uno usa lo que definen los anteriores. Este va al final: conecta la interfaz
   y pone todo en marcha (grafo, primer estado y WebSocket). */

// ================= Interfaz: leyenda, HUD movil y filtros =================
function abrirLeyenda(abierta) {
  $('leyenda').dataset.abierta = abierta;
  $('ley-toggle').setAttribute('aria-expanded', abierta);
}
// Abierta por defecto solo si el mapa tiene espacio; si no, queda a un toque en el boton "Leyenda"
abrirLeyenda(!movil.matches && $('mapa').clientWidth >= 900 && $('mapa').clientHeight >= 560);
$('ley-toggle').addEventListener('click', () => abrirLeyenda($('leyenda').dataset.abierta !== 'true'));
$('hud-toggle').addEventListener('click', () => {
  const abierto = $('hud').classList.toggle('abierto');
  $('hud-toggle').setAttribute('aria-expanded', abierto);
  if (abierto && movil.matches) abrirLeyenda(false);
});
$('ver-rutas').addEventListener('change', ev => {
  if (!capaRutas) return;
  if (ev.target.checked) capaRutas.addTo(mapa); else capaRutas.remove();
});
$('ver-dormidos').addEventListener('change', ev => $('mapa').classList.toggle('sin-dormidos', !ev.target.checked));

// ================= Arranque =================
// Diagnostico de solo lectura para la consola del navegador (cuantos marcadores hay en el mapa)
window.diagnosticoMapa = () => ({zombies: zombies.size, sobrevivientes: sobrevivientes.size, camionetas: camionetas.size,
  zonasHorda: zonas.size, bloqueadas: bloqueadas.size, refugios: refugios.size, animando: animados.size,
  calles: G.lineas.size, conexion: $('conexion').dataset.modo, turno: ultimo ? ultimo.turno : null});
setInterval(() => { if (ultimo) pintarEstadoRonda(); }, 250);
cargarGrafo();
pedirEstado();   // primer dato sin esperar al WebSocket
conectarWS();
