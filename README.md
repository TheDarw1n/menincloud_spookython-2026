# Escape de Manta Zombie · Track A (Spookython 2026)

Motor de rutas en AWS que recalcula en tiempo real según obstáculos móviles (zombies, calles bloqueadas) y responde rápido aunque cientos de sobrevivientes pidan ruta a la vez.

- **URL pública (mapa en vivo):** https://d160b5kavxovby.cloudfront.net
- **Endpoint del track:** `POST https://d160b5kavxovby.cloudfront.net/paso` (header `x-api-key`)
- **Arquitectura:** [`docs/arquitectura.png`](docs/arquitectura.png) (fuente editable: [`docs/arquitectura.drawio`](docs/arquitectura.drawio))
- **Costos:** [`docs/costos.md`](docs/costos.md) · **AWS Budget:** ![budget](docs/budget.png)

> Estado: 🚧 en construcción. El grafo actual es de **prueba (20 nodos)**; falta el export real de Manta.

## Equipo
| Persona | Responsabilidad |
|---|---|
| Kenneth | _(completar)_ |
| Jonathan | _(completar)_ |
| Jostin | _(completar)_ |

## Qué hace
1. Carga el mapa de Manta como grafo (intersecciones y calles con tipo y velocidad) y 4 refugios.
2. Cada turno (2 s) mueve a los zombies, publica el estado (`/estado` y `/ws`) y recalcula **una sola vez** las rutas: 1 Dijkstra inverso por refugio.
3. `POST /paso` solo consulta esas tablas: elige el vecino seguro con menor costo al refugio. Movimiento inválido, error o timeout = quedarse quieto.
4. Mapa en vivo (Leaflet): zombies por tipo, sobrevivientes, ruta planificada, calles bloqueadas y refugios.

## Arquitectura y decisiones
`Navegador → CloudFront (HTTPS, WAF) → S3 (frontend) | ALB → ECS Fargate (FastAPI + simulador, estado en memoria) → DynamoDB / SSM / CloudWatch`. Región **us-east-1** siempre.

- **Fargate y no Lambda:** sin arranques en frío y con el estado compartido en memoria de un solo proceso (la rúbrica penaliza estado por instancia).
- **Rutas calculadas por turno, no por petición:** `Mundo.asegurar_planner()` compara contra el turno **del servidor** con doble verificación bajo lock; el planner publica snapshots inmutables.
- **`/paso` como ruta ASGI directa:** sin pydantic ni inyección de dependencias (~0.43 ms de CPU por petición medido en el sandbox de desarrollo, frente a ~0.82 ms con FastAPI normal).
- **Sin Redis, NAT Gateway, API Gateway, Secrets Manager ni Location Service:** costo fijo innecesario.
- **Snapshots en DynamoDB:** cada 10 turnos y al terminar cada ronda (`pk=SNAPSHOT|RONDA`, `sk`=tiempo). `POST /ws/sim/reanudar` retoma el último snapshot tras un reinicio.

## Seguridad e IAM
- Usuarios IAM **individuales** (Kenneth, Jonathan, Jostin) con consola, cambio de contraseña obligatorio y **MFA**. Nadie usa root.
- Grupo `MantaTeam` con 9 políticas administradas (el límite por grupo es 10): ECS, ECR, DynamoDB, S3, CloudFront, CloudWatch, SSM, ELB y VPC. **Sin** AdministratorAccess, **sin** IAM, facturación ni Organizations. Política en línea `pasar-roles-ecs`: `iam:PassRole` solo sobre los 2 roles de ECS (condición `ecs-tasks`).
- Roles de la tarea (creados con root, única excepción): `manta-execution-role` (política de ejecución de ECS + lectura de `/manta/api-key`) y `manta-task-role` (`dynamodb:PutItem/GetItem/Query` solo sobre `manta-snapshots`).
- **API key** en SSM Parameter Store (SecureString), inyectada como variable `API_KEY`; nunca en el código ni en el repo. `/paso` y el control del simulador la exigen.
- **`/estado` y `/ws` son de lectura pública por defecto** (`PUBLIC_STATE=true`): el navegador no puede guardar una key sin exponerla y solo publican el estado visible del juego. Con `PUBLIC_STATE=false` exigen la key. ⚠️ **Verificar con los organizadores** si las reglas piden key también ahí.
- Contenedor con usuario no root. Security groups encadenados: CloudFront → `manta-sg-alb` (:80) → `manta-sg-tarea` (:8000).
- AWS Budget `manta-zombie-mensual`: 50 USD/mes, alertas 50/80/100 % (+ pronosticado) a 3 correos, sobre gasto **bruto** (sin créditos). **Avisa, no corta el gasto.**

## CloudFront plan Free: límites
- Máximo **5 cache behaviors** (ya usados: Default→S3, `/paso`, `/estado`, `/salud`, `/ws*`). No se pueden añadir rutas, por eso: el grafo se sirve como archivo estático de S3 (`/manta_graph.json`) y el control del simulador vive bajo `/ws/sim/*`.
- Sin access logs ni analytics (Pro); sin protección DDoS de capa 7 (Business). El **WAF incluido puede devolver 403 ante ráfagas** del simulador: probarlo con `latency.py` contra la URL de CloudFront y documentar el resultado aquí.
- **WebSocket vía CloudFront con este plan: SIN PROBAR.** Prueba: abrir el mapa y ver si el HUD dice "en vivo (WebSocket)"; si no, el frontend cae solo a polling de `/estado` cada 2 s.
- Price Class 100 no aplica (el plan usa todas las ubicaciones).

## Cómo probar en local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
API_KEY=dev SIM_MODO=directo uvicorn src.api.main:app --port 8000     # UN solo worker
curl -X POST localhost:8000/paso -H "x-api-key: dev" -H "content-type: application/json" \
  -d '{"sobrevivienteId":"S-0089","nodoActual":"N-0001","turno":1}'
curl -X POST "localhost:8000/ws/sim/iniciar?ronda=3" -H "x-api-key: dev"   # 1, 2, 3 o ciclo
curl -H "x-api-key: dev" localhost:8000/ws/sim/resultados
TURNO_S=0 python -m src.simulator.run_simulator 3                          # ronda completa sin HTTP
```
Variables: `API_KEY`, `PUBLIC_STATE`, `SIM_AUTOSTART` (none|1|2|3|ciclo), `SIM_MODO` (http|directo), `TURNO_S`, `TURNOS_RONDA`, `SNAPSHOTS_TABLE`, `GRAPH_PATH`, `ORIGIN_SECRET` (opcional).

## Contrato técnico
- `GET /estado` · `WS /ws` → `{turno, zombies[{id,tipo,nodo,previo,visible}], aristasBloqueadas[], sobrevivientes[], ronda, metricas}`
- `POST /paso` (`x-api-key`): `{sobrevivienteId, nodoActual, turno}` → `{siguienteNodo}`; `GET /salud` → health check.
- Reglas: turno de 2 s, primero zombies y luego sobrevivientes; cada sobreviviente avanza **un nodo** por turno; mordida si comparte nodo con un zombie o se cruzan por la misma calle; `/paso` debe responder en < 500 ms.

## Despliegue
Infraestructura creada **a mano en la consola** (sin IaC). Configuración de la tarea en [`infra/task-definition.json`](infra/task-definition.json).
```bash
./infra/deploy.sh            # backend (ECR + ECS + espera a estable) y frontend (S3 + invalidación)
./infra/deploy.sh backend | frontend
```
- `deploy.sh` usa `minimumHealthyPercent=0 / maximumPercent=100`: **nunca hay 2 tareas con estados distintos**, a costa de ~1 min de corte por despliegue.
- Construir ARM64 desde un PC x86 usa emulación (lento). Alternativa: `PLATFORM=linux/amd64 ./infra/deploy.sh backend` y cambiar `runtimePlatform` a `X86_64` en la task definition.
- **Credenciales de CLI:** cada persona que despliegue crea **UNA** access key de **su** usuario IAM (nunca de root, nunca en el repo) y la **borra al terminar el evento**. Una access key no está protegida por el MFA de la consola. Mejor: que despliegue solo una persona.
- **Cierre del evento:** borrar el ALB, bajar el servicio ECS a 0 (o borrarlo), borrar CloudFront y confirmar que no hay NAT. El ALB y Fargate cobran por hora.

## Latencia
- Objetivo p95 ≤ 150 ms. Guayaquil → us-east-1 añade ~100 ms de red: **medir también desde CloudShell en us-east-1** para separar red de servidor.
```bash
python -m src.simulator.latency https://d160b5kavxovby.cloudfront.net API_KEY --niveles 20,80,200 --turnos 10
```
- Mide con concurrencia real y nodos distintos, e imprime el puntaje de la rúbrica. **Pendiente medir en AWS** y pegar los resultados aquí.
- Medición en el sandbox de desarrollo (1 CPU compartida cliente+servidor): ~0.43 ms de CPU por `/paso`. Una ráfaga de 200 simultáneas serían ~90 ms de CPU en un núcleo completo y el doble en 0.5 vCPU, **al límite del umbral de 150 ms**. Si en AWS sale p95 alto, subir la tarea a 1 vCPU / 2 GB (~+14 USD/mes).
- `SIM_MODO=http` (default) hace que el simulador interno llame a `/paso` por localhost, pero comparte hilo y CPU con el servidor y mide peor que un jurado externo. `SIM_MODO=directo` evita ese costo para el demo del mapa.

## Limitaciones conocidas
- Tramo CloudFront → ALB en **HTTP** (sin dominio). Cualquier distribución de CloudFront podría llegar al ALB. Mitigación opcional ya implementada: variable `ORIGIN_SECRET` + header de origen `x-origin-verify` en CloudFront (no activada).
- Un solo contenedor con el estado en **memoria**: 1 worker de uvicorn (nunca `--workers > 1`). Un reinicio pierde el estado (se puede retomar con `/ws/sim/reanudar`).
- Sin IaC: infraestructura manual.
- Grafo actual de prueba (20 nodos). `tools/export_manta.py` (OSMnx) genera el real; **no pude probarlo** (sin acceso a OpenStreetMap desde mi entorno). Validar con `tools/validar_grafo.py`. Velocidades por tipo de calle y cantidades de zombies por ronda son propuestas ajustables (`src/world/graph.py`, `src/simulator/engine.py`).
- Cercanía a zombies: nodos con zombie visible y vecinos de hordas están prohibidos; los vecinos de un zombie visible cuestan +30 s (`Mundo.PENAL_S`, valor propuesto).
- Se usó root únicamente para crear los roles IAM.

## Estructura
```
src/api/        FastAPI: /paso (ruta rápida ASGI), /estado, /salud, /ws, /ws/sim/*
src/world/      grafo, mundo publicado, zombies, eventos, mordidas
src/routing/    Dijkstra inverso y planner (snapshots inmutables)
src/simulator/  engine (rondas 1-3), latency (carga), run_simulator (local sin HTTP)
src/persistence.py   snapshots/resultados en DynamoDB
tools/          export_manta.py (OSMnx) y validar_grafo.py
frontend/       mapa en vivo (Leaflet) · infra/ despliegue · docs/ arquitectura y costos · tests/
```

## Flujo de trabajo
Una rama por persona (`feat/...`), PR a `main`, un commit por hito probado.
