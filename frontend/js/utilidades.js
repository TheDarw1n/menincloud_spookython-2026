'use strict';
// Ayudas de formato, del DOM y de la rubrica que usan los archivos siguientes.

// ================= Utilidades =================
const $ = id => document.getElementById(id);
const movil = window.matchMedia('(max-width: 900px)');
const esNum = v => typeof v === 'number' && Number.isFinite(v);
const lista = v => Array.isArray(v) ? v : [];
const objeto = v => v && typeof v === 'object' && !Array.isArray(v) ? v : {};
const fmt0 = new Intl.NumberFormat('es-EC', {maximumFractionDigits: 0});
const fmt1 = new Intl.NumberFormat('es-EC', {maximumFractionDigits: 1});
const fmt2 = new Intl.NumberFormat('es-EC', {maximumFractionDigits: 2});
const entero = v => esNum(v) ? fmt0.format(v) : '0';
const pct = v => esNum(v) ? fmt1.format(v * 100) + ' %' : '—';
const pctDirecto = v => esNum(v) ? fmt2.format(v) + ' %' : '—';
const ms = v => esNum(v) ? fmt1.format(v) + ' ms' : '—';
const plural = (n, uno, varios) => `${fmt0.format(n)} ${n === 1 ? uno : varios}`;
const cmpIds = (a, b) => String(a).localeCompare(String(b), 'es', {numeric: true});
function poner(el, texto) { texto = String(texto); if (el && el.textContent !== texto) el.textContent = texto; }
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])); }
function mmss(milis) { const s = Math.max(0, Math.ceil(milis / 1000)); return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0'); }
function unirY(xs) { return xs.length < 2 ? xs.join('') : xs.slice(0, -1).join(', ') + ' y ' + xs[xs.length - 1]; }
const nivelNota = v => v >= 8 ? 'ok' : v >= 6 ? 'aviso' : v >= 4 ? 'serio' : 'critico';
function notaLatencia(p95) { if (!esNum(p95)) return null; return p95 <= 150 ? [10, 'ok'] : p95 <= 300 ? [7, 'aviso'] : p95 <= 500 ? [4, 'serio'] : [0, 'critico']; }
function notaErrores(p) { if (!esNum(p)) return null; return p < .5 ? [10, 'ok'] : p < 2 ? [6, 'aviso'] : p < 5 ? [3, 'serio'] : [0, 'critico']; }
function iconoEvento(texto, tipo) {
  if (tipo === 'puente') return '💥';
  if (tipo === 'avenida' || tipo === 'calle' || tipo === 'callejon') return '🚧';
  const t = ' ' + String(texto || '').toLowerCase();
  if (/despert|dormid/.test(t)) return '💤';
  if (/colaps|derrumb|\s(cay|caí)/.test(t)) return '💥';
  if (/puente/.test(t)) return '🌉';
  if (/bloque|cerr|cort/.test(t)) return '🚧';
  if (/horda/.test(t)) return '🧟';
  if (/refugio|lleno/.test(t)) return '🏠';
  return '⚠️';
}
function mostrarError(texto) {
  const el = $('aviso-error');
  if (el.hidden === !texto && el.textContent === texto) return;
  poner(el, texto); el.hidden = !texto;
  if (mapa) mapa.invalidateSize();  // el aviso ocupa espacio sobre el mapa
}
