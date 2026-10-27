"""Puntaje de la prueba de fuego del Track A (0-10), igual que la rubrica:
Supervivencia 50 % (ponderada R1 x1, R2 x2, R3 x3) - Eficiencia 20 % (turnos vs ruta mas corta
sin zombies) - Latencia 15 % (p95 de POST /paso) - Disponibilidad 15 % (errores o fuera de tiempo).
La eficiencia se pondera por ronda igual que la supervivencia (la rubrica no fija pesos)."""

PESO_RONDA = {1: 1, 2: 2, 3: 3}


def nota_latencia(p95_ms):
    return 10 if p95_ms <= 150 else 7 if p95_ms <= 300 else 4 if p95_ms <= 500 else 0


def nota_disponibilidad(pct):
    return 10 if pct < 0.5 else 6 if pct < 2 else 3 if pct < 5 else 0


def percentil(ordenados, p):
    if not ordenados:
        return None
    return ordenados[min(len(ordenados) - 1, int(len(ordenados) * p))]


def calcular(resultados, latencias):
    """resultados: {ronda: resultado de la ronda}; latencias: {ronda: [ms]} de esas corridas.
    Usa las rondas presentes con sus pesos; 'completo' indica si estan las 3."""
    rondas = sorted(r for r in resultados if r in PESO_RONDA)
    if not rondas:
        return None

    def ponderado(campo):
        pares = [(PESO_RONDA[r], resultados[r][campo]) for r in rondas if resultados[r].get(campo) is not None]
        return sum(p * v for p, v in pares) / sum(p for p, _ in pares) if pares else 0.0

    p95 = percentil(sorted(x for r in rondas for x in latencias.get(r, ())), 0.95)
    consultas = sum(resultados[r]["consultas"] for r in rondas)
    errores = sum(resultados[r]["errores_o_timeout"] for r in rondas)
    pct = 100 * errores / consultas if consultas else 0.0
    notas = {"supervivencia": round(10 * ponderado("supervivencia"), 2),
             "eficiencia": round(10 * ponderado("eficiencia"), 2),
             "latencia": nota_latencia(p95) if p95 is not None else 0,
             "disponibilidad": nota_disponibilidad(pct)}
    total = (0.5 * notas["supervivencia"] + 0.2 * notas["eficiencia"]
             + 0.15 * notas["latencia"] + 0.15 * notas["disponibilidad"])
    return {"total": round(total, 2), **notas,
            "latenciaP95": round(p95, 2) if p95 is not None else None, "pctErrores": round(pct, 3),
            "rondas": rondas, "completo": rondas == [1, 2, 3]}
