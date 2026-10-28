# Declaración de costos

> - **Región:** us-east-1. **Moneda:** USD, precios de lista **sin impuestos**.
> - **Precios verificados el 2026-10-27** contra los archivos oficiales de la AWS Price List API (publicados entre el 2026-09-11 y el 2026-10-26) y las páginas de precios y documentación de AWS (ver [Fuentes](#fuentes)).
> - **Costo bruto:** los créditos de la cuenta **no se restan**, porque no cambian lo que cuesta operar el sistema. Solo se aplican las asignaciones gratuitas **permanentes** que forman parte del precio publicado (por ejemplo, los primeros 25 GB de DynamoDB), y cada fila lo indica.
> - **Mes = 730 h.** Las cifras marcadas *(estimado)* son supuestos de uso. Las marcadas *(medido)* salen de correr el código del repositorio (versión del 2026-10-27, 11:02) con un grafo sintético de 306 nodos y 502 calles, parecido al de Manta. Los precios unitarios están todos verificados.

## Resumen

| Concepto | USD |
|---|---|
| Operar el sistema **24/7 durante un mes** | **≈ 41.86** |
| **Costo del evento:** 5 días (120 h), del 2026-10-26 al 2026-10-30 | **≈ 6.90** |
| **Gasto real del evento** según Cost Explorer | _pendiente: ver [sección 6](#6-gasto-real-durante-el-evento)_ |

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

**Fecha de corte:** ____________. Cost Explorer actualiza los datos al menos una vez cada 24 h, así que el último día puede estar incompleto. Para la entrega (2026-10-28 a las 10:00, hora de Ecuador, que son las 15:00 UTC) habrá datos como mucho hasta el 2026-10-27, y ese día puede estar incompleto. Conviene llenar la tabla con ese corte, indicarlo arriba y, si se permite, actualizarla después del cierre.

| Servicio en Cost Explorer | Estimado del evento (USD) | Real (USD) | Diferencia |
|---|---|---|---|
| Elastic Container Service (Fargate) | 2.37 | | |
| Elastic Load Balancing | 2.71 | | |
| Virtual Private Cloud (IPv4 públicas) | 1.80 | | |
| CloudFront | 0.00 | | |
| WAF | 0.00 | | |
| CloudWatch | 0.00 | | |
| DynamoDB | 0.01 | | |
| S3 | 0.00 | | |
| EC2 Container Registry (ECR) | 0.00 | | |
| Key Management Service / Systems Manager | 0.00 | | |
| EC2-Other (transferencia entre AZ) | 0.01 | | |
| Otros servicios que aparezcan | 0.00 | | |
| **Total** | **6.90** | | |

Si alguna diferencia supera ±20 %, anotar la causa debajo de la tabla (por ejemplo, días extra encendidos o una IP pública de más).

Captura de Cost Explorer: _pendiente del equipo_ (guardarla en `docs/gasto_real.png` con el paso 8 y enlazarla aquí).

**Cómo llenarla** (en la consola, sin costo):

1. **Permiso (una sola vez, con el usuario raíz).** En **Cuenta** (*Account*) → **Acceso de usuarios y roles de IAM a la información de facturación** (*IAM user and role access to Billing information*), elegir **Editar → Activar**. Después, crear un grupo `MantaFacturacionLectura` con la política administrada `AWSBillingReadOnlyAccess` y agregar **solo** a quien hará el reporte. No conviene usar el grupo `MantaTeam`: no tiene permisos de facturación y ya usa 9 de sus 10 políticas.
2. Abrir **Billing and Cost Management → Cost Explorer**.
3. **Rango de fechas:** personalizado, del **2026-10-26** al **2026-10-30** (o hasta la fecha de corte). **Granularidad:** diaria.
4. **Agrupar por:** Servicio.
5. **Filtros → Tipo de cargo (*Charge type*):** elegir la opción de **excluir** (*Exclude*) y marcar **Crédito (*Credit*)** y **Reembolso (*Refund*)**. Es el mismo criterio del Budget, que mide el gasto bruto. Los impuestos (*Tax*) solo aparecen con granularidad mensual; si salen, anotarlos aparte, porque los precios de esta hoja no los incluyen.
6. **Métrica:** costos no combinados (*Unblended costs*).
7. Copiar a la tabla el total de cada servicio (columna *Total* de la tabla que aparece bajo el gráfico) o descargar el CSV.
8. **Captura de pantalla:** que se vean el rango de fechas, el filtro de tipo de cargo y la tabla por servicio. Guardarla como **`docs/gasto_real.png`**.
9. **Verificación cruzada:** con el mismo rango, agrupar por **Tipo de uso** y ver la **cantidad de uso**. Por día debería aparecer:
   - ≈ 12 vCPU-h (`USE1-Fargate-ARM-vCPU-Hours:perCPU`) y ≈ 24 GB-h (`USE1-Fargate-ARM-GB-Hours`).
   - 24 h de ALB (`LoadBalancerUsage`).
   - **72 h de IPv4** (`USE1-PublicIPv4:InUseAddress`), que son 3 IP × 24 h.

   Si las IPv4 suman 96 h o más, hay una IP de más: una Elastic IP ociosa, un ALB que escaló o una tarea duplicada. Hay que revisarlo.

Alternativa por CLI (sin probar: no se ejecutó contra la cuenta). Cada llamada cuesta 0.01 USD y la fecha `End` no se incluye en el rango:

```bash
aws ce get-cost-and-usage --time-period Start=2026-10-26,End=2026-10-31 \
  --granularity DAILY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --filter '{"Not":{"Dimensions":{"Key":"RECORD_TYPE","Values":["Credit","Refund"]}}}'
```

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

## 9. Cierre del evento

El ALB, Fargate y las IPv4 cobran **por hora**, aunque nadie use el sistema: **1.374 USD/día**. Orden recomendado para apagar todo:

1. **Guardar la evidencia antes de borrar:** el resultado de `GET /ws/sim/resultados`, capturas del mapa y la tabla de Cost Explorer ([sección 6](#6-gasto-real-durante-el-evento)).
2. **ECS:** bajar el servicio a 0 tareas y borrarlo. Primero `aws ecs update-service --cluster manta --service manta-api --desired-count 0`, después `aws ecs delete-service --cluster manta --service manta-api`, y luego borrar el clúster `manta`. Esto detiene Fargate y libera la IP pública de la tarea.
3. **ALB:** borrar el load balancer y su target group. Así deja de cobrar los 0.0225 USD/h, las LCU y sus 2 IPv4.
4. **CloudFront:** en la distribución, **cancelar primero el plan Free**. Se cancela de inmediato, y mientras esté activo la distribución no se puede borrar. Después deshabilitarla, esperar a que termine de desplegarse y borrarla. Por último, **borrar el web ACL de WAF** asociado: fuera del plan pasaría a pago por uso (5 USD/mes + 1 USD por regla, prorrateado por hora).
5. **S3:** vaciar y borrar `frontend-manta`.
6. **DynamoDB:** exportar la tabla si hace falta y borrar `manta-snapshots`.
7. **ECR:** borrar el repositorio `manta-zombie` junto con sus imágenes.
8. **CloudWatch Logs:** borrar `/ecs/manta-zombie`, o dejar que expire a los 7 días.
9. **SSM:** borrar `/manta/api-key` y `/manta/admin-key`.
10. **VPC:** confirmar que no quedan NAT Gateway, Elastic IP sueltas (una IP ociosa también cobra 0.005 USD/h) ni ENI huérfanas.
11. **IAM:** borrar las access keys de cada usuario. Cuando ya no exista el servicio, borrar la política `pasar-roles-ecs` y los roles `manta-execution-role` y `manta-task-role`.
12. **Mantener el Budget**, que es gratis, hasta que cierre la factura del mes. Revisar Cost Explorer 48 h después: el costo diario debe quedar en ≈ 0.00 USD.

## Fuentes

Consultadas el 2026-10-27. Los archivos de la Price List API muestran su fecha de publicación.

**Archivos de la AWS Price List API (us-east-1):**

- Fargate: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/us-east-1/index.json (2026-10-19)
- ALB: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/us-east-1/index.json (2026-09-11)
- IPv4 pública y VPC endpoints: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/us-east-1/index.json (2026-10-16)
- NAT Gateway: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.json (2026-10-23)
- S3: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-1/index.json (2026-10-15)
- DynamoDB: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/us-east-1/index.json (2026-09-11)
- CloudWatch: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/us-east-1/index.json (2026-10-07)
- ECR: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECR/current/us-east-1/index.json (2026-09-11)
- Systems Manager: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSSystemsManager/current/us-east-1/index.json (2026-10-08)
- KMS: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/awskms/current/us-east-1/index.json (2026-10-26)
- Budgets: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSBudgets/current/index.json (2026-09-11)
- Cost Explorer: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSCostExplorer/current/us-east-1/index.json (2026-09-11)
- Transferencia de datos: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/us-east-1/index.json (2026-09-16)
- CloudFront, pago por uso: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudFront/current/index.json (2026-10-19)
- WAF: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/awswaf/current/us-east-1/index.json (2026-09-14)
- API Gateway: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonApiGateway/current/us-east-1/index.json (2026-10-13)
- ElastiCache: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonElastiCache/current/us-east-1/index.json (2026-10-14)
- Secrets Manager: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSSecretsManager/current/us-east-1/index.json (2026-09-11)

**Páginas de precios y documentación de AWS:**

- Fargate: https://aws.amazon.com/fargate/pricing/ (tarifas por segundo, mínimo de 1 minuto, 20 GB efímeros)
- ALB: https://aws.amazon.com/elasticloadbalancing/pricing/ (definición de LCU, hora parcial = hora completa)
- 1 IP por AZ habilitada: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html
- IPv4 en recursos de una VPC, incluido ECS: https://aws.amazon.com/vpc/pricing/
- IPv4 administradas por servicios (ELB): https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/ · https://aws.amazon.com/blogs/networking-and-content-delivery/identify-and-optimize-public-ipv4-address-usage-on-aws/
- CloudFront, planes de tarifa plana: https://aws.amazon.com/cloudfront/pricing/ · https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html (asignaciones, exceso, cuotas, cancelación y borrado)
- S3: https://aws.amazon.com/s3/pricing/
- DynamoDB on-demand: https://aws.amazon.com/dynamodb/pricing/on-demand/ · TTL: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html
- CloudWatch: https://aws.amazon.com/cloudwatch/pricing/ (capa gratuita) · EMF: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html
- ECR: https://aws.amazon.com/ecr/pricing/
- Systems Manager: https://aws.amazon.com/systems-manager/pricing/
- KMS: https://aws.amazon.com/kms/pricing/
- Budgets: https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/
- Cost Explorer: https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html · filtros: https://docs.aws.amazon.com/cost-management/latest/userguide/ce-filtering.html
- Acceso de IAM a la facturación: https://docs.aws.amazon.com/console/iam/billing-enable · https://repost.aws/knowledge-center/iam-billing-access
- Nueva capa gratuita con créditos (desde el 2025-07-15): https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/
