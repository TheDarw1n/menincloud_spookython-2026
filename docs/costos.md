# Declaración de costos

> - **Región:** us-east-1. **Moneda:** USD, precios de lista **sin impuestos**.
> - **Costo bruto:** los créditos de la cuenta **no se restan**, porque no cambian lo que cuesta operar el sistema. Solo se aplican las asignaciones gratuitas **permanentes** que forman parte del precio publicado (por ejemplo, los primeros 25 GB de DynamoDB), y cada fila lo indica.
> - **Mes = 730 h.** Las cifras marcadas *(estimado)* son supuestos de uso. Las marcadas *(medido)* salen de correr el código del repositorio (versión del 2026-10-27, 11:02) con un grafo sintético de 306 nodos y 502 calles.

## Resumen

| Concepto | USD |
|---|---|
| Operar el sistema **24/7 durante un mes** | **≈ 41.86** |
| **Costo del evento:** 5 días (120 h), del 2026-10-26 al 2026-10-30 | **≈ 6.90** |
| **Gasto real del evento** según Cost Explorer, al corte del 2026-10-28 a las 01:34 | **0.84** (ver [sección 6](#6-gasto-real-durante-el-evento)) |

**Cerca del 99 %** del costo es **fijo por hora** y no depende del tráfico: Fargate + ALB + 3 IPv4 públicas = **0.05725 USD/h = 1.374 USD/día**. Todo el tráfico de la prueba de fuego cuesta centavos.

## 1. Qué se está costeando

- **ECS Fargate:** 1 tarea **ARM64 (Graviton) de 0.5 vCPU y 1 GB** (`infra/task-definition.json`) con 1 worker de uvicorn, en una subred pública con IP pública. Usa los 20 GB de almacenamiento efímero incluidos. La task definition del repositorio está **reconstruida**: si la de la consola tiene otra CPU o memoria, hay que recalcular las filas de Fargate.
- **Application Load Balancer** expuesto a internet en **2 AZ**, con 1 IP pública por AZ.
- **CloudFront en plan Free** (WAF incluido) con dos orígenes: S3 (`frontend-manta`, con el mapa en `index.html`, `css/` y `js/`, y `manta_graph.json`) y el ALB.
- **DynamoDB on-demand** (`manta-snapshots`, TTL de 7 días), **SSM Parameter Store** (`/manta/api-key` y `/manta/admin-key`, SecureString con la clave administrada `aws/ssm`), **CloudWatch Logs** (`/ecs/manta-zombie`, 7 días), **ECR** (`manta-zombie`) y el **AWS Budget** `manta-zombie-mensual`.
- **No se usan:** NAT Gateway, API Gateway, ElastiCache, Secrets Manager, Route 53 ni dominio propio. Se asume que Container Insights está **desactivado**.

## 2. Precios unitarios verificados (us-east-1)

| Servicio | Precio | Notas |
|---|---|---|
| Fargate Linux/ARM | **0.03238 USD** por vCPU-hora · **0.00356 USD** por GB-hora | Se cobra por segundo, con un mínimo de 1 minuto. En x86 serían 0.04048 y 0.004445. Incluye 20 GB de almacenamiento efímero. |
| Application Load Balancer | **0.0225 USD** por hora o fracción · **0.008 USD** por LCU-hora | 1 LCU equivale a 25 conexiones nuevas/s, 3 000 conexiones activas/min, 1 GB/h procesado (destinos IP o contenedor) o 1 000 evaluaciones de reglas/s (las 10 primeras reglas son gratis). Cada hora se cobra solo la dimensión más alta. |
| IPv4 pública | **0.005 USD** por IP-hora, en uso u ociosa | Esta arquitectura usa **3**: la ENI de la tarea y 1 por cada AZ del ALB. |
| CloudFront, plan Free | **0 USD/mes** por distribución | Incluye **1 M de peticiones y 100 GB al mes**, WAF (hasta 5 reglas), 5 cache behaviors, WebSockets y 5 GB de crédito para S3. No incluye access logs (desde el plan Pro). **No hay cobro por exceso:** llegan avisos al 50, 80 y 100 %, y el primer pico de hasta 3× no afecta el servicio ese mes. Un exceso sostenido (se evalúa en 2–3 meses o más) puede degradar la entrega hasta que se suba de plan. Las peticiones que bloquea el WAF no cuentan. Hay un máximo de 3 planes Free por cuenta. |
| S3 Standard | **0.023 USD/GB-mes** · **0.005 USD** por 1 000 PUT/LIST · **0.0004 USD** por 1 000 GET | La transferencia de S3 a CloudFront cuesta 0 USD. |
| DynamoDB on-demand | **0.625 USD** por millón de WRU · **0.125 USD** por millón de RRU · **0.25 USD/GB-mes** | Los primeros 25 GB de almacenamiento son gratis. Cada escritura consume 1 WRU por KB, redondeado hacia arriba. Los borrados por TTL no consumen escrituras. |
| CloudWatch Logs | **0.50 USD/GB** ingerido (clase Standard) · **0.03 USD/GB-mes** almacenado · **0.005 USD/GB** consultado con Logs Insights | Capa gratuita: 5 GB (ingesta, almacenamiento y consultas). |
| CloudWatch, métricas y alarmas | **0.30 USD** por métrica-mes (primeras 10 000), prorrateado por hora · **0.10 USD** por alarma-mes (resolución estándar) | Las métricas que generan EMF o los filtros de métricas sobre los logs se cobran como métricas personalizadas, además de la ingesta del log. Cada combinación de dimensiones cuenta como una métrica aparte. Las primeras 10 métricas y 10 alarmas son gratis. |
| ECR | **0.10 USD/GB-mes** | La transferencia de ECR a Fargate en la misma región cuesta 0 USD. |
| SSM Parameter Store estándar | **0 USD** | No se cobra por guardar el parámetro ni por la API con rendimiento estándar. La clave de KMS administrada por AWS (`aws/ssm`) no tiene cuota mensual; sus solicitudes cuestan 0.03 USD por cada 10 000 y las primeras 20 000 del mes son gratis. |
| AWS Budgets | **0 USD** | Los presupuestos sin acciones son gratis. Con acciones: 2 gratis y luego 0.10 USD/día. Cada informe cuesta 0.01 USD. |
| Cost Explorer | **0 USD** en la consola | Por API: 0.01 USD por solicitud. |
| Transferencia de datos | ALB → CloudFront **0.00 USD/GB** · entre AZ **0.01 USD/GB** | Entre Fargate y DynamoDB o ECR, dentro de la misma región: 0 USD. |

**Precios de referencia de lo que *no* usamos** (también verificados): NAT Gateway 0.045 USD/h + 0.045 USD/GB · VPC endpoint de interfaz 0.01 USD/h por AZ + 0.01 USD/GB · API Gateway HTTP API 1.00 USD por millón de peticiones (REST: 3.50) · ElastiCache `cache.t4g.micro` 0.0128 USD/h con Valkey (0.016 con Redis OSS) · Secrets Manager 0.40 USD por secreto al mes · WAF fuera del plan: 5 USD por web ACL al mes + 1 USD por regla al mes + 0.60 USD por millón de peticiones · CloudFront en pago por uso: 1 TB y 10 M de peticiones gratis al mes, y después 0.0100 USD por cada 10 000 peticiones HTTPS (EE. UU.).

## 3. Supuestos de carga

**Prueba de fuego:** R1 = 20 × 150 = 3 000 · R2 = 80 × 150 = 12 000 · R3 = 200 × 150 = 30 000. En total, **45 000 `POST /paso` en unos 15 minutos**. El pico es de 200 peticiones por turno de 2 s, es decir, 100 peticiones/s.

**Tamaños *(medido)*** con el código del repositorio y el grafo sintético de 306 nodos. Con el mapa real pueden variar ±50 %.

| Dato | R1 | R2 | R3 |
|---|---|---|---|
| `/estado` o mensaje del WebSocket, por turno | 3.7 KB | 11.0 KB | 25.8 KB (máx. 38.3) |
| Snapshot en DynamoDB (cada 10 turnos) | 3.7 KB = 4 WRU | 10.1 KB = 11 WRU | 20.9 KB = 21 WRU |
| WRU por ronda (15 snapshots y el resultado) | 61 | 166 | 316 |

Otros tamaños medidos:

- `POST /paso`: 67 B de cuerpo en la petición y 27 B en la respuesta.
- `manta_graph.json`: unos 81 KB. El mapa en vivo (`index.html`, `css/` y `js/`, 12 archivos): 86 KB en total. Se suben con `Cache-Control: no-cache`, así que en cada visita el navegador los revalida y, si no cambiaron, recibe un 304 sin cuerpo.
- El log de acceso de uvicorn está **desactivado** (`--no-access-log` en el `Dockerfile`): antes eran unos 60 B por cada petición.
- Logs JSON del simulador (una línea cada 10 turnos, más el resultado y el puntaje de cada ronda): unos 11 KB por simulacro.
- Un simulacro completo (3 rondas) escribe **543 WRU**, es decir, 0.0003 USD.

**Uso del evento *(estimado)*:**

- **`POST /paso` por CloudFront:** 330 000, que salen de la prueba del jurado y 5 ensayos completos (6 × 45 000) más 20 corridas de `latency.py` (20 × 3 000).
- **Resto del tráfico por CloudFront:** 300 cargas del mapa (3 peticiones cada una), 20 pestañas-hora en modo polling (1 800 peticiones por hora) y 200 peticiones de control. Con eso, el evento suma **≈ 367 000 peticiones y ≈ 0.89 GB**.
- **Simulador interno:** además se cuentan 20 ciclos con `SIM_MODO=http`. Van por localhost, así que no pasan por CloudFront ni por el ALB, pero sí escriben logs.

**¿Cabe en el plan Free de CloudFront (1 M de peticiones y 100 GB)?**

| Escenario | Peticiones al mes por CloudFront | ¿Cabe? |
|---|---|---|
| Solo el evento (lo de arriba) | ≈ 0.37 M · 0.89 GB | **Sí**: 37 % de las peticiones y menos del 1 % de los datos. |
| Demo continua: el simulacro de 3 rondas en bucle 24/7 con clientes externos | 45 000 × 4 ciclos/h × 730 h = **131.4 M** | **No** (131 veces la asignación). Haría falta como mínimo el plan Business (200 USD/mes, 125 M), o el Premium (1 000 USD/mes, 500 M). En pago por uso serían ≈ 121 USD de peticiones y ≈ 87 USD de WAF. |
| Carga máxima sostenida: 200 por turno, 24/7 | 100/s × 3 600 × 730 = **262.8 M** | **No** (263 veces). |
| Demo continua con el simulador interno | 0 de `/paso`, porque van por localhost | **Sí, pero solo si el mapa usa WebSocket.** Una sola pestaña en modo polling 24/7 suma 1.31 M al mes (ya se pasa), y cada visor recibe ≈ 18 GB al mes. |

## 4. Costo mensual 24/7

La infraestructura queda encendida las 730 h, con el mismo tráfico del evento.

| Servicio (nombre aproximado en Cost Explorer) | Cálculo | USD/mes |
|---|---|---|
| Fargate vCPU (Elastic Container Service) | 0.5 vCPU × 0.03238 USD/h × 730 h | 11.82 |
| Fargate memoria (Elastic Container Service) | 1 GB × 0.00356 USD/h × 730 h | 2.60 |
| ALB por hora (Elastic Load Balancing) | 1 ALB × 0.0225 USD/h × 730 h | 16.43 |
| ALB por LCU (Elastic Load Balancing) *(estimado)* | ≈ 5 LCU-h × 0.008 USD. Son ≈ 0.07 LCU en las horas con rondas (≈ 200 conexiones activas desde CloudFront) y ≈ 0 en reposo. | 0.04 |
| IPv4 públicas (Amazon Virtual Private Cloud) | 3 IP × 0.005 USD/h × 730 h | 10.95 |
| CloudFront + WAF (plan Free) | 0.37 M de 1 M peticiones; 0.89 GB de 100 GB | 0.00 |
| S3 | 0.1 MB × 0.023 USD/GB + ≈ 100 PUT/LIST × 0.005/1 000 + ≈ 1 000 GET × 0.0004/1 000. El plan Free da 5 GB de crédito. | < 0.01 |
| DynamoDB on-demand | 26 simulacros × 543 WRU = 14 118 WRU × 0.625 USD/M. Guarda 14 MB (menos de los 25 GB gratis). | 0.01 |
| CloudWatch Logs *(estimado)* | Sin log de acceso: solo los logs JSON del simulador, 26 simulacros × 11 KB ≈ 0.3 MB × 0.50 USD/GB. Con 7 días de retención, el almacenamiento es ≈ 0. | < 0.01 |
| CloudWatch, métricas y alarmas | Supuesto: 10 métricas o menos, creadas con filtros de métricas sobre los logs JSON o con EMF (por ejemplo, p95, % de errores y supervivencia por ronda), y 10 alarmas o menos. Cada métrica extra cuesta 0.30 USD/mes y cada alarma extra, 0.10 USD/mes. **No usar `sobrevivienteId` como dimensión.** | 0.00 |
| ECR *(estimado)* | ≈ 0.1 GB de capas × 0.10 USD/GB-mes | 0.01 |
| SSM Parameter Store + KMS | El parámetro estándar no se cobra. Hay ≈ 30 descifrados al mes (1 por cada arranque de la tarea), muy por debajo de los 20 000 gratis. | 0.00 |
| AWS Budgets | 1 presupuesto sin acciones | 0.00 |
| Transferencia de datos *(estimado)* | ALB → CloudFront y S3 → CloudFront: 0. Entre AZ: ≈ 1 GB × 0.01 USD/GB. | 0.01 |
| **Total** | **41.79 fijos + 0.07 variables** | **≈ 41.86** |

_Los totales se calculan sin redondear cada fila._

**Variantes:**

- Subir la tarea a **1 vCPU y 2 GB** (si en AWS el p95 sale alto) cuesta **+14.42 USD/mes**: Fargate pasa a 28.84 USD.
- La misma tarea en **x86** cuesta +3.60 USD/mes.
- Link de AWS Pricing Calculator: 
https://calculator.aws/#/estimate?id=cd92ee02de11a28f6bdf4853cd3c05745f0feac8 

**Por qué la calculadora da 48.52 USD/mes:** tiene los mismos servicios que esta hoja, pero con supuestos de uso más altos en cuatro filas:

- **Elastic Load Balancing (22.27):** equivale a 1 LCU todas las horas (5.84 USD). Con el tráfico del evento son ≈ 5 LCU-h al mes (0.04 USD), así que el ALB queda en ≈ 16.47.
- **CloudWatch (0.61):** supone 1 GB de logs al mes, 1 GB consultado con Logs Insights, 1 alarma y 70 eventos OTel. Sin el log de acceso se escriben ≈ 0.3 MB al mes, las primeras 10 alarmas son gratis y el sistema no usa OTel: < 0.01 USD.
- **DynamoDB (0.22):** supone ítems de 30 KB. El snapshot más grande medido pesa 20.9 KB, y con lo medido (543 WRU por simulacro) sale ≈ 0.01 USD al mes.
- **ECR (0.05):** supone 0.5 GB guardados. Esta hoja estima ≈ 0.1 GB (0.01 USD).

Con los datos de esta hoja, la calculadora daría ≈ 41.9 USD/mes.

## 5. Costo del evento (del 2026-10-26 al 2026-10-30)

Son 5 días × 24 h = **120 h**. AWS cuenta los días en UTC. **Cada día adicional encendido suma 1.374 USD.**

| Servicio | Cálculo | USD |
|---|---|---|
| Fargate | (0.5 × 0.03238 + 1 × 0.00356) USD/h × 120 h = 0.01975 × 120 | 2.37 |
| ALB por hora | 0.0225 USD/h × 120 h | 2.70 |
| ALB por LCU *(estimado)* | ≈ 1.5 LCU-h × 0.008 USD | 0.01 |
| IPv4 públicas | 3 × 0.005 USD/h × 120 h | 1.80 |
| CloudFront + WAF (plan Free) | 0.37 M de peticiones, 0.89 GB | 0.00 |
| S3 | Igual que en el mes | < 0.01 |
| DynamoDB | 14 118 WRU × 0.625 USD/M | 0.01 |
| CloudWatch Logs *(estimado)* | Solo logs JSON del simulador (sin log de acceso) ≈ 0.3 MB × 0.50 USD/GB | < 0.01 |
| ECR *(estimado)* | 0.1 GB × 0.10 USD × 120/730 | < 0.01 |
| Transferencia *(estimado)* | ≈ 1 GB entre AZ × 0.01 USD/GB | 0.01 |
| **Total** | **6.87 fijos + 0.03 variables** | **≈ 6.90** |

Si la infraestructura se creó antes del 2026-10-26, hay que sumar 1.374 USD por cada día anterior.

## 6. Gasto real durante el evento

*Corte de datos:* miércoles 28 de octubre de 2026, 01:34 (hora de Ecuador).
*Fuente:* AWS Cost Explorer, rango 2026-10-26 a 2026-10-28, agrupado por servicio.
*Filtro:* Tipo de cargo = Usage + Tax (sin Credit), es decir, *gasto bruto* antes de aplicar créditos.
*Captura:* [gasto_real.png](gasto_real.png)

| Servicio | USD acumulado al corte |
|---|---|
| Elastic Load Balancing (ALB) | 0.54 |
| VPC (principalmente direcciones IPv4 públicas) | 0.19 |
| Elastic Container Service (Fargate) | 0.11 |
| DynamoDB, ECR, S3, CloudFront (plan Free), CloudWatch, KMS, CloudShell, CloudFormation, Glue | 0.00 |
| *Total real al corte* | *0.84* |

La cuenta usa créditos promocionales, por lo que el monto facturado neto es 0.00 USD; aquí se
declara el gasto bruto. El valor es *parcial*: Cost Explorer puede tardar hasta ~24 h en reflejar
el gasto más reciente, y las fechas del informe están en UTC.

El gasto es bajo porque el servicio de cómputo (ECS Fargate) estuvo apagado o con pocas horas de
ejecución; casi todo corresponde a recursos fijos por hora (ALB e IPv4 públicas).

### Proyección hasta el pitch (viernes 30 de octubre)
Con Fargate, ALB y las IPv4 públicas encendidos: ~1.5 USD por día (ver cálculo en la sección anterior).
Desde el corte hasta el pitch quedan ~2.5 días, es decir ~3.8 USD adicionales.

*Gasto total estimado del evento: ~4.6 USD.* El valor final se confirmará con Cost Explorer
después del pitch.

## 7. Decisiones que bajaron el costo

| Decisión | Alternativa evitada | Ahorro |
|---|---|---|
| **Sin NAT Gateway.** La tarea está en una subred pública con IP pública, y su security group solo acepta tráfico desde el del ALB. | NAT Gateway: 0.045 × 730 = 32.85 USD/mes + 0.045 USD/GB. Otra opción serían 4 VPC endpoints de interfaz (ECR api, ECR dkr, Logs y SSM) × 2 AZ = 58.40 USD/mes. | ≈ 29 USD/mes (32.85 menos los 3.65 de la IP de la tarea) |
| **Sin API Gateway.** El tráfico va directo de CloudFront al ALB. | HTTP API a 1.00 USD por millón: 0.33 USD en el evento y 131 USD/mes en una demo continua. Además agrega un salto de red. | 0.33–131 USD |
| **Sin ElastiCache.** El estado vive en la memoria de un solo proceso. | `cache.t4g.micro` sin réplica: 9.34 USD/mes con Valkey, 11.68 con Redis OSS. | ≈ 9–12 USD/mes |
| **Sin Secrets Manager.** La API key está en Parameter Store como SecureString. | 0.40 USD por secreto al mes + 0.05 USD por 10 000 llamadas. | 0.40 USD/mes |
| **Una sola tarea ARM (Graviton).** | La misma tarea en x86 cuesta 18.02 USD/mes. Una segunda tarea duplicaría Fargate y obligaría a compartir el estado. | 3.60 USD/mes (−20 %) |
| **CloudFront en plan Free.** | En pago por uso, el CDN también costaría 0 a este volumen (1 TB y 10 M de peticiones gratis), pero el WAF costaría 5 USD por web ACL + 1 USD por regla: ≈ 8 USD/mes con 3 reglas. | ≈ 8 USD/mes |
| **Logs con retención de 7 días.** | Con retención indefinida, el almacenamiento (0.03 USD/GB-mes) se acumularía mes a mes. | Centavos hoy; evita que crezca |
| **DynamoDB on-demand**, con un snapshot cada 10 turnos y TTL de 7 días. | Capacidad provisionada ociosa, o un snapshot por turno (10 veces más escrituras). | 543 WRU por simulacro = 0.0003 USD |
| **AWS Budget de 50 USD** con alertas al 50, 80 y 100 % sobre el gasto bruto. | — | Es gratis. Avisa, pero **no corta** el gasto. |

**Ya aplicado:** uvicorn escribía una línea de log por cada petición (unos 60 B): en una demo continua serían ≈ 7.9 GB/mes (≈ 3.94 USD/mes). El `CMD` del `Dockerfile` usa `--no-access-log` y quedan solo los errores y los logs JSON del simulador (uno cada 10 turnos y uno por ronda).

### Lo que todavía se podría recortar y por qué no se hizo

| Opción | Ahorro en el evento (120 h) | Ahorro al mes 24/7 | Por qué no se hizo |
|---|---|---|---|
| **Quitar el ALB** y apuntar CloudFront directo a la tarea | ≈ 3.91 USD: ALB 2.70 + LCU 0.01 + 2 IPv4 1.20 | ≈ 23.77 USD: 16.43 + 0.04 + 7.30 | El rendimiento sería el mismo (hay un salto menos), pero se pierde la recuperación automática. CloudFront exige un nombre de dominio como origen y una tarea Fargate no admite una IP fija: cada reinicio (despliegue, caída o mantenimiento de AWS) le cambia la dirección, y el sistema queda caído hasta que alguien actualiza el origen a mano. Hoy el ALB registra solo la tarea nueva. La disponibilidad pesa 15 % en la rúbrica. |
| **Tarea de 0.25 vCPU y 0.5 GB** | ≈ 1.19 USD | ≈ 7.21 USD | Pierde rendimiento: la API, el simulador y el planner comparten la mitad de CPU, y el p95 de 14–17 ms con todo a la vez se midió con 0.5 vCPU. |
| **Fargate Spot** | — | — | AWS puede retirar la tarea con 2 minutos de aviso. Se perdería la ronda en curso, que se retoma a mano con `/ws/sim/reanudar`. |
| **Quitar la IP pública de la tarea** | ≈ 0.60 USD | ≈ 3.65 USD | Sin IP, la tarea no puede descargar la imagen de ECR ni leer SSM. Haría falta un NAT Gateway (32.85 USD/mes) o 4 endpoints en 2 AZ (58.40 USD/mes): sale más caro. |
| **Dejar el ALB sin IP pública** (interno, conectado a CloudFront con *VPC origins*) | ≈ 1.20 USD (2 IPv4) | ≈ 7.30 USD | El plan Free de CloudFront no incluye *VPC origins*: empiezan en el plan Business, de 200 USD/mes ([precios de CloudFront](https://aws.amazon.com/cloudfront/pricing/)). En pago por uso, el WAF costaría ≈ 8 USD/mes, más de lo que se ahorra. |

Con esta arquitectura, lo único que se puede quitar sin perder rendimiento es el ALB, y el precio es la recuperación automática: el evento bajaría de ≈ 6.90 a ≈ 2.99 USD y el mes 24/7, de ≈ 41.86 a ≈ 18.09 USD. No lo hicimos porque el evento cuesta ≈ 6.90 USD de un Budget de 50. El ahorro que sí importa es apagar todo al terminar ([sección 9](#9-cierre-del-evento)): cada día de más encendido cuesta 1.374 USD.

## 8. Qué cambiaría a mayor escala

**Con 10 veces más sobrevivientes** (2 000 `/paso` por turno, es decir, ráfagas de 1 000 peticiones/s):

- **CPU.** Con 200 consultas por turno, la CI mide un p95 de 14–16 ms en ARM64 con 0.5 vCPU (también con 200 consultas externas y 30 visores a la vez): cada ráfaga se atiende en decenas de milisegundos. Con 2 000 por turno la ráfaga es 10 veces más larga *(estimado: del orden de 200 ms por turno)*, así que el p95 pasaría el umbral de 150 ms. Un proceso de Python con 1 worker (obligatorio mientras el estado viva en memoria) no aprovecha más de 1 vCPU. **Agrandar la tarea no basta.**
- **Estado compartido.** Habría que repartir `/paso` en varias réplicas, y eso exige compartir el estado. Hay dos opciones:
  - el planner calcula las tablas una vez por turno y las publica (Valkey `cache.t4g.micro`, 9.34 USD/mes);
  - cada réplica recalcula a partir del estado del turno, que son 4 Dijkstra sobre unos 300 nodos y sale barato.

  En ambos casos se pierde la regla actual del despliegue («nunca dos tareas a la vez»), y las tablas tendrían que llevar el número de turno para que ninguna réplica responda con datos viejos.
- **Costo *(estimado)*.** 4 tareas ARM de 1 vCPU y 2 GB (4 × 28.835 = 115.34 USD) + ALB (16.43) + 6 IPv4 (4 tareas y 2 del ALB: 6 × 3.65 = 21.90) + Valkey (9.34) ≈ **163 USD/mes**. A eso se suman las LCU: unas 3.6 por cada hora de carga (1 KB × 1 000 peticiones/s ≈ 3.6 GB/h), lo que daría 21 USD/mes si la carga fuera continua.
- **CloudFront.** Un simulacro a esta escala son 450 000 peticiones. Con algunos ensayos se pasa de 1 M, así que haría falta el plan Pro (15 USD/mes, 10 M).
- **DynamoDB.** El snapshot crecería a unos 210 KB, más de la mitad del límite de 400 KB por ítem. Habría que comprimirlo, partirlo o guardarlo en S3.
- **Logs.** El log de acceso ya está quitado; a esa escala sería imprescindible.

**Con una demo continua 24/7 y tráfico externo:**

- CloudFront tendría que pasar a los planes Business o Premium (200–1 000 USD/mes), o a pago por uso (≈ 208 USD/mes entre peticiones y WAF).
- Los logs costarían ≈ 3.94 USD/mes sin `--no-access-log` (ya aplicado).
- DynamoDB costaría ≈ 0.97 USD/mes.