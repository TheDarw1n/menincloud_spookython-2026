'use strict';
// Panel lateral: ronda, contadores, metricas, puntaje, eventos, refugios y resultados.

// ================= HUD =================
let firmaEventos = '', firmaPuntaje = '', firmaRefugios = '', firmaResultados = '';
const eventosVistos = new Set();

function pintarHUD(e, turnoNuevo) {
  const m = objeto(e.metricas);
  const info = RONDAS[e.ronda];
  const turno = esNum(e.turno) ? e.turno : 0, tr = restantes(e);
  // Sin numero de ronda (backend antiguo) pero con turnos: se habla de "la simulacion"
  const sinNumero = e.ronda == null && turno > 0;
  poner($('ronda-titulo'), info ? `Ronda ${e.ronda} · ${info.nombre}` : e.ronda != null ? `Ronda ${e.ronda}` : sinNumero ? 'Simulación de Manta' : 'Sin ronda en curso');
  poner($('ronda-desc'), info ? info.desc : sinNumero ? 'Cada 2 s los zombies se mueven y el motor recalcula la ruta de cada sobreviviente.' : 'El operador todavía no inicia la prueba.');
  poner($('hb-ronda'), info ? `R${e.ronda} · ${info.nombre}` : e.ronda != null ? `Ronda ${e.ronda}` : sinNumero ? 'Simulación' : 'Sin ronda');
  poner($('turno'), fmt0.format(turno));
  const total = tr != null ? turno + tr : null;
  poner($('turno-total'), total ? ` de ${fmt0.format(total)}` : '');
  $('prog-ronda').style.width = total ? (100 * turno / total).toFixed(1) + '%' : '0%';
  if (turnoNuevo) reiniciarPulso();

  poner($('c-salvados'), entero(m.salvados)); poner($('hb-salvados'), entero(m.salvados));
  poner($('c-mordidos'), entero(m.mordidos)); poner($('hb-mordidos'), entero(m.mordidos));
  poner($('c-rechazados'), entero(m.rechazados));
  poner($('c-camioneta'), entero(m.rescatadosEnCamioneta));
  const sob = lista(e.sobrevivientes), zs = lista(e.zombies).filter(Boolean), cams = lista(e.camionetas);
  const dormidos = zs.filter(z => z.visible === false || z.tipo === 'dormido').length;
  // El backend real no publica a los dormidos (son invisibles): solo informa cuantos hay
  const ocultos = !dormidos && esNum(m.dormidosOcultos) && m.dormidosOcultos > 0 ? m.dormidosOcultos : 0;
  $('filtro-dormidos').hidden = !dormidos;
  const aBordo = esNum(m.aBordo) && m.aBordo > 0 ? ` con ${plural(m.aBordo, 'persona', 'personas')} a bordo` : '';
  poner($('en-mapa'), `En el mapa: ${plural(sob.length, 'sobreviviente', 'sobrevivientes')} · ${plural(zs.length - dormidos, 'zombie visible', 'zombies visibles')}` +
    (dormidos ? ` · ${plural(dormidos, 'dormido', 'dormidos')}` : '') + (ocultos ? ` · ${plural(ocultos, 'dormido oculto', 'dormidos ocultos')}` : '') +
    (cams.length ? ` · ${plural(cams.length, 'camioneta', 'camionetas')}${aBordo}` : ''));

  const salv = esNum(m.salvados) ? m.salvados : 0, mord = esNum(m.mordidos) ? m.mordidos : 0;
  poner($('m-superv'), esNum(m.supervivencia) ? pct(m.supervivencia) : salv + mord ? pct(salv / (salv + mord)) : '—');
  poner($('m-efic'), pct(m.eficiencia));
  pintarNota('m-lat', ms(m.latenciaP95), notaLatencia(m.latenciaP95));
  pintarNota('m-err', pctDirecto(m.pctErrores), notaErrores(m.pctErrores));
  poner($('m-consultas'), esNum(m.consultas) ? `${fmt0.format(m.consultas)} consultas a POST /paso en esta ronda` : '');

  pintarPuntaje(e.puntaje);
  if (Array.isArray(e.eventos)) pintarEventos(e.eventos);
  pintarListaRefugios(datosRefugios(e));
  if (Array.isArray(e.resultados)) pintarResultados(e.resultados);
  pintarEstadoRonda();
}

function pintarNota(id, texto, nota) {
  poner($(id), texto);
  const ins = $(id + '-n');
  ins.hidden = !nota;
  if (nota) { poner(ins, `${nota[0]}/10`); ins.dataset.nivel = nota[1]; ins.title = `Puntos de la rúbrica: ${nota[0]} de 10`; }
}

function reiniciarPulso() {
  const barra = $('prog-turno');
  barra.style.transition = 'none'; barra.style.width = '0%';
  if (!corriendoAhora()) return;
  void barra.offsetWidth;
  barra.style.transition = `width ${TURNO_MS}ms linear`; barra.style.width = '100%';
}

// Se llama en cada estado y cada 250 ms: reloj, chip de la ronda y mensaje de espera
function pintarEstadoRonda() {
  const e = ultimo, corriendo = corriendoAhora();
  const turno = e && esNum(e.turno) ? e.turno : 0, tr = restantes(e);
  const reloj = tr == null || (!corriendo && turno === 0) ? '--:--'
    : mmss(tr * TURNO_MS - (corriendo ? Math.min(TURNO_MS, Date.now() - tTurno) : 0));
  poner($('tiempo'), reloj); poner($('hb-tiempo'), reloj);
  const [estado, texto] = corriendo ? ['curso', 'En curso'] : turno > 0 ? (tr === 0 ? ['fin', 'Terminada'] : ['pausa', 'Detenida']) : ['espera', 'En espera'];
  const chip = $('ronda-chip');
  if (chip.dataset.estado !== estado) { chip.dataset.estado = estado; poner(chip, texto); if (!corriendo) reiniciarPulso(); }
  const vacio = $('vacio');
  vacio.hidden = corriendo;
  if (corriendo) return;
  const info = e && RONDAS[e.ronda];
  if (turno > 0) {
    vacio.dataset.modo = 'fin';
    const quien = e.ronda != null ? `La ronda ${e.ronda}${info ? ' · ' + info.nombre : ''}` : 'La simulación';
    poner($('vacio-texto'), `${quien} ${tr === 0 ? 'terminó' : 'se detuvo'} en el turno ${turno}. El mapa muestra cómo quedó.`);
  } else {
    vacio.dataset.modo = 'inicio';
    poner($('vacio-texto'), 'Cuando empiece, aquí verás moverse a los zombies y a los sobrevivientes turno a turno.');
  }
}

const COMPONENTES = [['supervivencia', 'Supervivencia', '50 %'], ['eficiencia', 'Eficiencia', '20 %'], ['latencia', 'Latencia', '15 %'], ['disponibilidad', 'Disponibilidad', '15 %']];
function pintarPuntaje(p) {
  const hay = !!p && typeof p === 'object' && esNum(p.total);
  $('puntaje').hidden = !hay; $('puntaje-vacio').hidden = hay;
  if (!hay) return;
  poner($('p-total'), fmt1.format(p.total));
  $('p-total').dataset.nivel = nivelNota(p.total);
  const html = COMPONENTES.map(([k, nombre, peso]) => {
    const v = esNum(p[k]) ? p[k] : null;
    return `<li><span>${nombre} <small>${peso}</small></span><span class="medidor"><i data-nivel="${v == null ? '' : nivelNota(v)}" style="width:${v == null ? 0 : Math.max(0, Math.min(100, v * 10))}%"></i></span><b>${v == null ? '—' : fmt1.format(v)}</b></li>`;
  }).join('');
  if (html !== firmaPuntaje) { $('p-comp').innerHTML = html; firmaPuntaje = html; }
  const rs = lista(p.rondas).map(String);
  poner($('p-rondas'), rs.length ? `Calculado con ${rs.length === 1 ? 'la ronda' : 'las rondas'} ${unirY(rs)}.` : '');
}

function claveEvento(ev) { return `${ev.turno}|${ev.texto}|${ev.arista}`; }
function pintarEventos(evs) {
  evs = lista(evs).filter(ev => ev && (ev.texto || ev.arista));
  const firma = evs.map(claveEvento).join('#');
  if (firma === firmaEventos) return;
  firmaEventos = firma;
  const ol = $('eventos');
  ol.textContent = '';
  if (!evs.length) {
    ol.innerHTML = '<li class="sub">Sin eventos por ahora. Aquí aparecerán los puentes que colapsan y las calles que se bloquean.</li>';
    return;
  }
  for (const ev of evs.slice().reverse()) {
    const clave = claveEvento(ev), nuevo = !eventosVistos.has(clave);
    const texto = ev.texto || `Calle bloqueada (${ev.arista})`;
    const li = document.createElement('li');
    li.className = 'evento' + (nuevo && !primerEstado ? ' nuevo' : '');
    li.innerHTML = `<span class="ev-t">${ev.turno != null ? 'T' + esc(ev.turno) : '—'}</span><span class="ev-i" aria-hidden="true">${iconoEvento(texto, ev.tipo)}</span><span></span>`;
    li.lastChild.textContent = texto;
    ol.appendChild(li);
    if (nuevo) {
      eventosVistos.add(clave);
      if (!primerEstado) { aviso(ev.turno, texto, ev.tipo); if (ev.arista != null) setTimeout(() => destacarArista(ev.arista), 50); }
    }
  }
}

function aviso(turno, texto, tipo) {
  const caja = $('toasts');
  const div = document.createElement('div');
  div.className = 'toast';
  div.setAttribute('role', 'status');
  div.innerHTML = `<span class="toast-i" aria-hidden="true">${iconoEvento(texto, tipo)}</span><div><b>Turno ${esc(turno ?? '?')}</b> · <span class="toast-x"></span></div>`;
  div.querySelector('.toast-x').textContent = texto;
  caja.prepend(div);
  while (caja.children.length > 2) caja.lastChild.remove();  // no tapar media ciudad con avisos
  setTimeout(() => div.classList.add('saliendo'), 6500);
  setTimeout(() => div.remove(), 7100);
}

function pintarListaRefugios(datos) {
  let html;
  if (!datos.length) html = '<li class="sub">Sin datos de refugios todavía.</li>';
  else html = datos.map(r => {
    const color = colorRefugio(String(r.id));
    const cap = esNum(r.capacidad) && r.capacidad > 0 ? r.capacidad : null, oc = esNum(r.ocupacion) ? r.ocupacion : null;
    const cab = `<li title="${esc(r.id)}${esNum(r.evacuaPorTurno) ? ` · evacúa ${esc(r.evacuaPorTurno)} por turno` : ''}"><span class="punto-ref" style="background:${color}"></span><span class="lr-nom">${esc(r.nombre || r.id)}</span>`;
    if (cap == null || oc == null) return cab + '<span class="lr-num">sin datos de capacidad</span></li>';
    const f = Math.min(1, oc / cap), nivel = oc >= cap ? 'lleno' : f >= .8 ? 'alto' : 'ok';
    const etiqueta = nivel === 'lleno' ? ' · <b class="lr-lleno">Lleno</b>' : nivel === 'alto' ? ' · <b class="lr-alto">Casi lleno</b>' : '';
    const puerta = r.enPuerta ? `<span class="lr-puerta">${plural(r.enPuerta, 'persona espera', 'personas esperan')} en la puerta</span>` : '';
    return cab + `<span class="lr-num">${fmt0.format(oc)}/${fmt0.format(cap)}${etiqueta}</span><span class="medidor"><i data-nivel="${nivel}" style="width:${(f * 100).toFixed(0)}%"></i></span>${puerta}</li>`;
  }).join('');
  if (html !== firmaRefugios) { $('lista-refugios').innerHTML = html; firmaRefugios = html; }
}

function pintarResultados(res) {
  res = lista(res).filter(r => r && typeof r === 'object');
  $('resultados-tarjeta').hidden = !res.length;
  const html = res.map(r => {
    const lat = esNum(r.latenciaP95) ? r.latenciaP95 : objeto(r.latencia_ms).p95;
    const err = esNum(r.pctErrores) ? r.pctErrores : r.pct_errores;
    const nombre = RONDAS[r.ronda] ? RONDAS[r.ronda].nombre : '';
    return `<tr><td title="${esc(nombre)}">${esc(r.ronda ?? '?')}</td><td>${entero(r.salvados)}</td><td>${entero(r.mordidos)}</td><td>${pct(r.supervivencia)}</td><td>${pct(r.eficiencia)}</td><td>${esNum(lat) ? fmt1.format(lat) : '—'}</td><td>${pctDirecto(err)}</td></tr>`;
  }).join('');
  if (html !== firmaResultados) { $('resultados').innerHTML = html; firmaResultados = html; }
}
