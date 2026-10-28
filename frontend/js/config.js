'use strict';
// Constantes del mapa en vivo. No depende de ningun otro archivo.

// ================= Configuracion =================
const TURNO_MS = 2000, ANIM_MS = 1500, POLL_MS = 2000;
// WebSocket: espera del handshake, reintentos (se duplican si el socket dura poco) y silencio maximo
// (en ronda llega un estado por turno; fuera de ronda solo un ping cada ~20 s)
const WS_ESPERA_MS = 4000, WS_REINTENTO_MS = 10000, WS_REINTENTO_MAX_MS = 60000;
const WS_SILENCIO_RONDA_MS = 10000, WS_SILENCIO_MS = 45000;
const RONDAS = {
  1: {nombre: 'Anochecer', desc: '20 sobrevivientes · solo zombies caminantes'},
  2: {nombre: 'Medianoche', desc: '80 sobrevivientes · caminantes, corredores y hordas · colapsa un puente'},
  3: {nombre: 'Apocalipsis', desc: '200 sobrevivientes a la vez · todos los zombies · se bloquean dos calles'},
};
const ZOMBIE = {
  caminante: {nombre: 'Caminante', html: '<span>🧟</span>'},
  corredor: {nombre: 'Corredor', html: '<span>🧟</span><i class="rayo">⚡</i>'},
  horda: {nombre: 'Horda', html: '<span class="h1">🧟</span><span class="h2">🧟</span><span class="h3">🧟</span>'},
  dormido: {nombre: 'Dormido', html: '<span>💤</span>'},
};
// Colores por refugio en orden fijo (validados para daltonismo); el 5.o en adelante es gris
const COLORES_REFUGIO = ['#3987e5', '#eab308', '#d55181', '#e9ecef'];
const COLOR_SIN_REFUGIO = '#9a98b8';
const ESTILO_CALLE = {
  avenida: {color: '#a78bfa', weight: 4.5, opacity: .9},
  calle: {color: '#7c6cc4', weight: 2.5, opacity: .8},
  callejon: {color: '#5d5592', weight: 1.5, opacity: .85},
  puente: {color: '#4fd1c5', weight: 6, opacity: 1},
};
// Calle bloqueada: barrera roja a trazos sobre un borde oscuro, por encima de rutas y zonas
const ESTILO_BLOQUEADA = {color: '#ff5c5c', weight: 5, opacity: 1, dashArray: '7 6', lineCap: 'butt'};
const ESTILO_BLOQUEADA_FONDO = {color: '#0b0b1a', weight: 9, opacity: .9, lineCap: 'butt'};
