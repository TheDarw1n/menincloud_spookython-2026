"""Tabla Markdown con los resultados de /ws/sim/resultados (para el README o el resumen de CI).
Uso: curl -s URL/ws/sim/resultados -H "x-api-key: KEY" | python tools/resumen_resultados.py"""
import json
import sys


def main():
    d = json.load(sys.stdin)
    print("| Ronda | Turnos | Salvados | Mordidos | Supervivencia | Eficiencia | En camioneta | Rechazos | p95 /paso (ms) | Errores |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in d.get("resultados", []):
        print(f"| {r['ronda']} {r.get('nombre', '')} | {r['turnos']} | {r['salvados']} | {r['mordidos']} | "
              f"{r['supervivencia']} | {r.get('eficiencia')} | {r.get('rescatados_en_camioneta', 0)} | "
              f"{r.get('rechazados', 0)} | {r['latencia_ms']['p95']} | {r['pct_errores']} % |")
    p = d.get("puntaje")
    if p:
        print(f"\n**Puntaje de la prueba de fuego: {p['total']} / 10** (supervivencia {p['supervivencia']}, "
              f"eficiencia {p['eficiencia']}, latencia {p['latencia']}, disponibilidad {p['disponibilidad']}; "
              f"p95 {p['latenciaP95']} ms, errores {p['pctErrores']} %, rondas {p['rondas']})")


if __name__ == "__main__":
    main()
