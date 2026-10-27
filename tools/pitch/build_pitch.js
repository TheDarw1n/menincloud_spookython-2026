// Genera docs/pitch.pptx (pitch de 5 minutos, Track A Spookython 2026), con notas del orador.
// Uso: npm install pptxgenjs@3.12.0 && PPTX_SKILL=<carpeta con scripts/apply_theme.js> node tools/pitch/build_pitch.js .
// Las cifras salen de la CI (prueba de carga en 0.5 vCPU) y de tools/ab_planner.py; actualizarlas si cambian.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const REPO = process.argv[2];
const SALIDA = path.join(REPO, "docs", "pitch.pptx");
const img = (rel) => path.join(REPO, rel);
const existe = (rel) => fs.existsSync(img(rel));

const THEME = {
  name: "Manta Zombie Noche",
  headFontFace: "Bookman Old Style",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B0B1A", lt1: "FFFFFF", dk2: "1E1A3A", lt2: "D9D3F5",
    accent1: "F6AD55", accent2: "8B5CF6", accent3: "34D399", accent4: "F87171",
    accent5: "60A5FA", accent6: "FBBF24", hlink: "F6AD55", folHlink: "C4B5FD",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "Escape de Manta Zombie · Pitch Track A";
pres.author = "Jonathan Cruz, Kenneth Salazar, Jostin Moran";
pres.subject = "Spookython 2026 · Track A";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const FONDO = { color: C.text1 }; // azul noche
const PIE = "Escape de Manta Zombie · Spookython 2026 · Track A";

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "PORTADA",
  background: FONDO,
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 2.0, w: 6.9, h: 1.9, fontFace: THEME.headFontFace,
      fontSize: 44, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 4.05, w: 6.9, h: 1.6, fontFace: THEME.bodyFontFace,
      fontSize: 20, color: C.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENIDO",
  background: FONDO,
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.95, fontFace: THEME.headFontFace,
      fontSize: 34, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: PIE, options: { x: 0.6, y: 6.95, w: 8, h: 0.3, fontFace: THEME.bodyFontFace, fontSize: 10,
      color: C.background2, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 6.95, w: 0.5, h: 0.3, fontFace: THEME.bodyFontFace, fontSize: 10, color: C.background2, align: "right" },
});

// ---------- piezas ----------
function tarjeta(slide, nombre, x, y, w, h) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { objectName: nombre, x, y, w, h, rectRadius: 0.12,
    fill: { color: C.text2 }, line: { color: C.accent2, width: 1, transparency: 55 } });
}
function icono(slide, nombre, emoji, x, y, color, d = 0.62) {
  slide.addShape(pres.shapes.OVAL, { objectName: nombre + "_circulo", x, y, w: d, h: d, fill: { color }, line: { type: "none" } });
  slide.addText(emoji, { objectName: nombre + "_emoji", x, y, w: d, h: d, align: "center", valign: "middle",
    fontFace: "Segoe UI Emoji", fontSize: Math.round(d * 30), margin: 0, isTextBox: true });
}
function texto(slide, nombre, t, opts) {
  slide.addText(t, { objectName: nombre, isTextBox: true, margin: 0, fontFace: THEME.bodyFontFace, color: C.background1, ...opts });
}
function cifra(slide, nombre, valor, etiqueta, x, y, w, color) {
  texto(slide, nombre + "_valor", valor, { x, y, w, h: 0.95, fontSize: 48, bold: true, color, fontFace: THEME.headFontFace });
  texto(slide, nombre + "_etiqueta", etiqueta, { x, y: y + 0.95, w, h: 0.75, fontSize: 14, color: C.background2, valign: "top" });
}

// ---------- 1. portada ----------
pres.addSection({ title: "Apertura" });
let s = pres.addSlide({ masterName: "PORTADA", sectionTitle: "Apertura" });
s.addText("Escape de Manta Zombie", { placeholder: "title" });
s.addText([
  { text: "Un motor de rutas en AWS que esquiva zombies en tiempo real", options: { breakLine: true } },
  { text: "Track A · Spookython 2026", options: { color: C.accent1, bold: true, breakLine: true } },
  { text: "Jonathan Cruz · Kenneth Salazar · Jostin Moran", options: { fontSize: 16 } },
], { placeholder: "body" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { objectName: "marco_mapa", x: 7.85, y: 0.9, w: 4.95, h: 5.7, rectRadius: 0.15,
  fill: { color: C.background1 }, line: { color: C.accent1, width: 2 } });
s.addImage({ objectName: "grafo_manta", path: img("docs/grafo_manta.png"), x: 7.95, y: 1.4, w: 4.75, h: 3.38,
  altText: "Grafo vial de Manta con barrios y refugios" });
texto(s, "pie_mapa", "Manta real: 307 intersecciones de OpenStreetMap, 4 barrios atrapados y 4 refugios en zonas altas",
  { x: 8.1, y: 5.0, w: 4.45, h: 1.2, fontSize: 14, color: C.text1, valign: "top" });
s.addNotes("31 de octubre: Manta amanece infestada. Hay sobrevivientes atrapados en Tarqui, Los Esteros, Barbasquillo y Jocay, y nuestro sistema es la única radio que les queda: les dice, paso a paso, por dónde ir. Somos Jonathan, Kenneth y Jostin, y en 5 minutos les mostramos cómo lo resolvimos y cuánto puntúa.");

// ---------- 2. el problema ----------
pres.addSection({ title: "Problema" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Problema" });
s.addText("El mapa cambia mientras te mueves", { placeholder: "title" });
texto(s, "tesis", "Calcular una ruta es fácil. Recalcularla cada 2 segundos para 200 personas a la vez, con zombies que caminan, corren y bloquean calles, en menos de 500 ms, no lo es.",
  { x: 0.6, y: 1.45, w: 12.1, h: 1.0, fontSize: 20, color: C.background2 });
const usos = [
  ["🛵", "Delivery y taxis", "La ruta se rehace con cada calle cerrada o accidente, para cientos de pedidos a la vez.", C.accent1],
  ["🚑", "Ambulancias", "Despachar la unidad correcta y esquivar el tráfico en vivo: segundos que salvan vidas.", C.accent4],
  ["🌊", "Evacuación", "Tsunamis en la costa de Manabí: cambia «zombie» por «zona inundada» y es una ruta de evacuación.", C.accent5],
];
usos.forEach(([e, t, d, col], i) => {
  const x = 0.6 + i * 4.13;
  tarjeta(s, `uso_${i}`, x, 2.75, 3.85, 3.15);
  icono(s, `uso_${i}_icono`, e, x + 0.35, 3.1, col, 0.8);
  texto(s, `uso_${i}_titulo`, t, { x: x + 0.35, y: 4.1, w: 3.2, h: 0.5, fontSize: 20, bold: true, fontFace: THEME.headFontFace });
  texto(s, `uso_${i}_texto`, d, { x: x + 0.35, y: 4.65, w: 3.2, h: 1.55, fontSize: 15, color: C.background2, valign: "top" });
});
s.addNotes("El reto no es Dijkstra: es que el mapa cambia mientras la gente se mueve. Es el núcleo de Uber, de las apps de delivery y de una ruta de evacuación ante tsunamis aquí en Manabí. Si cambiamos zombie por calle cerrada o zona inundada, el mismo motor sirve.");

// ---------- 3. solucion ----------
pres.addSection({ title: "Solución" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Solución" });
s.addText("Manta real, cada 2 segundos", { placeholder: "title" });
const pasos = [
  ["🧟", "1. Se mueven los zombies", "Caminantes, corredores que persiguen, hordas que bloquean y dormidos invisibles.", C.accent4],
  ["🧠", "2. El planner recalcula una vez", "4 Dijkstra inversos (uno por refugio) con los zombies del turno: ≈ 3 ms.", C.accent2],
  ["📡", "3. 200 sobrevivientes piden POST /paso", "Cada respuesta solo consulta las tablas del turno: ≈ 3 µs de cálculo.", C.accent1],
  ["🏠", "4. Mordidas y llegadas", "El simulador valida cada movimiento y lleva el puntaje de la rúbrica en vivo.", C.accent3],
];
pasos.forEach(([e, t, d, col], i) => {
  const y = 1.5 + i * 1.32;
  tarjeta(s, `paso_${i}`, 0.6, y, 7.0, 1.15);
  icono(s, `paso_${i}_icono`, e, 0.82, y + 0.24, col, 0.68);
  texto(s, `paso_${i}_titulo`, t, { x: 1.7, y: y + 0.12, w: 5.75, h: 0.45, fontSize: 18, bold: true });
  texto(s, `paso_${i}_texto`, d, { x: 1.7, y: y + 0.55, w: 5.75, h: 0.5, fontSize: 14, color: C.background2, valign: "top" });
});
const mapa = existe("docs/mapa_en_vivo.png") ? "docs/mapa_en_vivo.png" : "docs/grafo_manta.png";
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { objectName: "marco_mapa_vivo", x: 7.9, y: 1.5, w: 4.8, h: 5.11, rectRadius: 0.12,
  fill: { color: C.text2 }, line: { color: C.accent1, width: 2 } });
const altoMapa = existe("docs/mapa_en_vivo.png") ? 2.875 : 3.27;
s.addImage({ objectName: "mapa_vivo", path: img(mapa), x: 8.0, y: 1.6, w: 4.6, h: altoMapa,
  altText: "Mapa en vivo con zombies, sobrevivientes, rutas y refugios" });
texto(s, "mapa_pie", "Mapa en vivo: zombies por tipo, rutas planificadas, camionetas, cupos de refugios y puntaje en vivo. WebSocket con respaldo de polling.",
  { x: 8.15, y: 1.6 + altoMapa + 0.2, w: 4.3, h: 1.5, fontSize: 15, color: C.background2, valign: "top" });
s.addNotes("Cada turno: primero se mueven los zombies; el planner recalcula UNA sola vez, no por petición: un Dijkstra inverso por refugio. Después los 200 sobrevivientes preguntan POST /paso y cada respuesta es solo una consulta a esas tablas. Al final el simulador valida, cuenta mordidas y llegadas, y el mapa se actualiza en vivo.");

// ---------- 4. como decide ----------
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Solución" });
s.addText("Cómo decide cada paso", { placeholder: "title" });
tarjeta(s, "prohibido", 0.6, 1.5, 5.95, 4.95);
icono(s, "prohibido_icono", "⛔", 0.9, 1.8, C.accent4, 0.7);
texto(s, "prohibido_titulo", "Nunca pisa", { x: 1.8, y: 1.85, w: 4.5, h: 0.6, fontSize: 22, bold: true, fontFace: THEME.headFontFace });
texto(s, "prohibido_lista", [
  { text: "Un nodo con zombie visible", options: { bullet: true, breakLine: true } },
  { text: "La horda y TODOS sus vecinos", options: { bullet: true, breakLine: true } },
  { text: "Una calle cerrada (puente colapsado, avenida bloqueada)", options: { bullet: true, breakLine: true } },
  { text: "Cruzarse con un zombie por la misma calle (incluye los 2 pasos de un corredor)", options: { bullet: true } },
], { x: 0.95, y: 2.75, w: 5.35, h: 3.5, fontSize: 18, paraSpaceAfter: 10, valign: "top" });
tarjeta(s, "costo", 6.75, 1.5, 5.95, 4.95);
icono(s, "costo_icono", "🧭", 7.05, 1.8, C.accent1, 0.7);
texto(s, "costo_titulo", "Elige el menor costo", { x: 7.95, y: 1.85, w: 4.5, h: 0.6, fontSize: 22, bold: true, fontFace: THEME.headFontFace });
texto(s, "costo_lista", [
  { text: "Distancia ÷ velocidad del tipo de calle (avenida 50, calle 30, puente 40 km/h)", options: { bullet: true, breakLine: true } },
  { text: "+ 30 s por intersección: cada calle es un turno (eficiencia sin zombies 0.86 → 0.98)", options: { bullet: true, breakLine: true } },
  { text: "+ penalización solo en las TRAMPAS: donde un zombie puede caer el próximo turno sin dejar salida", options: { bullet: true, breakLine: true } },
  { text: "Test: 0 mordidas evitables en rondas completas", options: { bullet: true, bold: true, color: C.accent3 } },
], { x: 7.1, y: 2.75, w: 5.35, h: 3.5, fontSize: 18, paraSpaceAfter: 10, valign: "top" });
s.addNotes("Reglas duras: nunca pisa un zombie, ni la horda ni sus vecinos, ni una calle cerrada, y nunca se cruza con un zombie por la misma calle. Entre lo permitido elige el menor costo: distancia y tipo de calle, más 30 segundos por intersección, porque en el juego cada calle es un turno. Y un test juega rondas completas y exige cero mordidas evitables.");

// ---------- 5. resultados ----------
pres.addSection({ title: "Resultados" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Resultados" });
s.addText("Resultados medidos, no prometidos", { placeholder: "title" });
cifra(s, "puntaje", "9.56", "de 10 en la rúbrica: 3 rondas en un contenedor de 0.5 vCPU (CI)", 0.6, 1.5, 2.85, C.accent1);
cifra(s, "p95", "20 ms", "p95 de POST /paso en la ronda 3, 200 a la vez (umbral 150 ms)", 3.6, 1.5, 2.85, C.accent3);
cifra(s, "errores", "0 %", "errores o respuestas de más de 500 ms", 0.6, 3.5, 2.85, C.accent3);
cifra(s, "supervivencia", "98 %", "supervivencia en la ronda 3: 200 a la vez, todos los zombies", 3.6, 3.5, 2.85, C.accent5);
texto(s, "resultados_pie", "Rondas de 150 turnos, grafo de Manta, 6 semillas: supervivencia+eficiencia 6.54 de 7 (tools/ab_planner.py).",
  { x: 0.6, y: 5.6, w: 5.85, h: 0.8, fontSize: 14, color: C.background2, valign: "top" });
s.addChart(pres.charts.BAR, [{
  name: "Supervivencia + eficiencia (de 7)",
  labels: ["Base (sin PRO)", "Sin costo por intersección", "Sin flota", "Sin predicción", "Producción"],
  values: [6.282, 6.339, 6.478, 6.502, 6.539],
}], {
  objectName: "grafico_ab", x: 6.75, y: 1.45, w: 5.95, h: 5.0, barDir: "bar",
  chartColors: ["8B5CF6", "8B5CF6", "8B5CF6", "8B5CF6", "F6AD55"],
  showTitle: true, title: "A/B del planner: supervivencia + eficiencia (de 7)", titleFontSize: 14, titleColor: "FFFFFF",
  titleFontFace: "+mn-lt",
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: "FFFFFF", dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt",
  dataLabelFormatCode: "0.00",
  valAxisMinVal: 6.0, valAxisMaxVal: 6.7, valAxisLabelColor: "D9D3F5", valAxisLabelFontSize: 11, valAxisLabelFontFace: "+mn-lt",
  valAxisLabelFormatCode: "0.0", valGridLine: { color: "3A345E", size: 0.75 },
  catAxisLabelColor: "FFFFFF", catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catGridLine: { style: "none" },
  showLegend: false, plotArea: { fill: { color: "1E1A3A" } }, chartArea: { fill: { color: "1E1A3A" }, roundedCorners: false },
  barGapWidthPct: 60,
});
s.addNotes("Todo esto está medido. En la CI de GitHub levantamos el contenedor con la misma CPU que Fargate, 0.5 vCPU, y jugamos las 3 rondas por HTTP: 9.56 de 10, p95 de 20 ms con 200 a la vez y cero errores. A la derecha, el A/B: cada pieza del diseño suma, y la versión final es la mejor.");

// ---------- 6. PRO ----------
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "Resultados" });
s.addText("Nivel PRO, con su efecto medido", { placeholder: "title" });
const pro = [
  ["🏃", "Predicción de corredores", "Replica su persecución (2 calles por turno hacia el más cercano a ≤ 3) y evita las trampas.",
    "R2: −19 % mordidas, eficiencia 0.80 → 0.82", C.accent4],
  ["🏥", "Capacidad de refugios", "Cada refugio tiene cupo y evacúa por turno; el planner reparte según el cupo a la hora de llegada.",
    "−82 % llegadas a refugios llenos (R2+R3)", C.accent3],
  ["🚐", "Flota de rescate", "5 camionetas, 2 calles por turno, 4 plazas: el servidor decide a quién recoger y en qué orden.",
    "R3: ≈ 450 rescates por ronda, eficiencia 0.70 → 0.74", C.accent1],
];
pro.forEach(([e, t, d, dato, col], i) => {
  const x = 0.6 + i * 4.13;
  tarjeta(s, `pro_${i}`, x, 1.5, 3.85, 4.6);
  icono(s, `pro_${i}_icono`, e, x + 0.35, 1.85, col, 0.8);
  texto(s, `pro_${i}_titulo`, t, { x: x + 0.35, y: 2.85, w: 3.2, h: 0.85, fontSize: 20, bold: true, fontFace: THEME.headFontFace, valign: "top" });
  texto(s, `pro_${i}_texto`, d, { x: x + 0.35, y: 3.7, w: 3.2, h: 1.6, fontSize: 15, color: C.background2, valign: "top" });
  texto(s, `pro_${i}_dato`, dato, { x: x + 0.35, y: 5.05, w: 3.2, h: 0.85, fontSize: 16, bold: true, color: col, valign: "top" });
});
s.addNotes("Hicimos los tres extras y medimos cada uno en el mapa real. Predicción: replicamos la persecución del corredor y evitamos solo las trampas, no cualquier cercanía, porque alejarse de todo alarga las rutas y termina mordiendo más. Capacidad: repartimos según el cupo que tendrá cada refugio cuando llegues. Flota: cinco camionetas que el servidor despacha cada turno.");

// ---------- 7. arquitectura ----------
pres.addSection({ title: "AWS" });
s = pres.addSlide({ masterName: "CONTENIDO", sectionTitle: "AWS" });
s.addText("AWS barato, seguro y sin arranques en frío", { placeholder: "title" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { objectName: "marco_arquitectura", x: 0.6, y: 1.45, w: 7.85, h: 5.05, rectRadius: 0.1,
  fill: { color: C.background1 }, line: { color: C.accent2, width: 1.5 } });
s.addImage({ objectName: "arquitectura", path: img("docs/arquitectura.png"), x: 0.7, y: 1.55, w: 7.65, h: 4.78,
  altText: "Arquitectura en AWS: CloudFront, S3, ALB, ECS Fargate, DynamoDB, SSM, CloudWatch" });
cifra(s, "costo_mes", "41.86 USD", "al mes 24/7 · ≈ 6.90 USD los 5 días del evento", 8.75, 1.45, 4.0, C.accent1);
texto(s, "aws_lista", [
  { text: "Fargate, no Lambda: estado en memoria y sin arranques en frío", options: { bullet: true, breakLine: true } },
  { text: "Sin NAT, API Gateway ni Redis: ~40 USD/mes menos", options: { bullet: true, breakLine: true } },
  { text: "2 keys en SSM: la del jurado solo sirve para /paso", options: { bullet: true, breakLine: true } },
  { text: "IAM individual con MFA y Budget de 50 USD con alertas", options: { bullet: true } },
], { x: 8.75, y: 3.45, w: 4.0, h: 3.0, fontSize: 15, paraSpaceAfter: 6, valign: "top" });
s.addNotes("La arquitectura: CloudFront, S3 para el mapa, un ALB y una sola tarea Fargate ARM con el estado en memoria, así no hay arranques en frío ni estado repartido en Lambdas. Sin NAT, sin API Gateway, sin Redis: 42 dólares al mes encendido todo el tiempo y unos 7 dólares durante el evento. Seguridad: dos keys, la del jurado solo sirve para pedir pasos, y usuarios IAM con MFA.");

// ---------- 8. cierre ----------
pres.addSection({ title: "Cierre" });
s = pres.addSlide({ masterName: "PORTADA", sectionTitle: "Cierre" });
s.addText("De zombies a tsunamis", { placeholder: "title" });
s.addText([
  { text: "El mismo motor sirve para evacuar la costa de Manabí: cambia «zombie» por «zona inundada».", options: { breakLine: true } },
  { text: "d160b5kavxovby.cloudfront.net", options: { color: C.accent1, bold: true, breakLine: true } },
  { text: "github.com/TheDarw1n/menincloud_spookython-2026", options: { fontSize: 16 } },
], { placeholder: "body" });
tarjeta(s, "proximos", 7.85, 1.6, 4.95, 3.9);
texto(s, "proximos_titulo", "Lo que sigue", { x: 8.2, y: 1.9, w: 4.3, h: 0.6, fontSize: 22, bold: true, fontFace: THEME.headFontFace });
texto(s, "proximos_lista", [
  { text: "Zonas de inundación reales de la Secretaría de Gestión de Riesgos en vez de zombies", options: { bullet: true, breakLine: true } },
  { text: "Varias réplicas compartiendo las tablas de cada turno", options: { bullet: true, breakLine: true } },
  { text: "App móvil que guía a cada persona paso a paso", options: { bullet: true } },
], { x: 8.2, y: 2.65, w: 4.3, h: 2.7, fontSize: 17, color: C.background2, paraSpaceAfter: 10, valign: "top" });
s.addNotes("Cerramos donde empezamos: esto no es solo un juego. Con zonas de inundación reales en vez de zombies, es una ruta de evacuación para Manabí. El sistema está desplegado y todo el código, los tests y las mediciones están en el repositorio. ¡Gracias! ¿Preguntas?");

(async () => {
  await pres.writeFile({ fileName: SALIDA });
  await applyTheme(SALIDA, THEME);
  console.log("escrito", SALIDA);
})().catch((e) => { console.error(e); process.exit(1); });
