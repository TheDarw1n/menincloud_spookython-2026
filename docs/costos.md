# Declaración de costos

> Cifras de precios públicos de AWS (us-east-1) calculadas a mano con 730 h/mes. **Verificarlas en AWS Pricing Calculator antes de entregar** y pegar aquí el enlace del cálculo.
> Los créditos de la cuenta **no cambian** el costo declarado: aquí va el costo real de operar, aunque a nosotros no nos lo cobren.

## Costo mensual si el sistema queda encendido 24/7
| Servicio | Configuración | USD/mes aprox. |
|---|---|---|
| ECS Fargate | ARM64, 0.5 vCPU, 1 GB, 1 tarea (0.5×0.03238 + 1×0.00356 USD/h) | ~14.4 |
| Application Load Balancer | 1 ALB (0.0225 USD/h) + LCU mínimas | ~17–22 |
| **IPv4 públicas** | 0.005 USD/h c/u: 1 de la tarea + 1 por AZ del ALB (2 AZ) = 3 | ~11 (≈3.65 c/u) |
| CloudFront | **Plan flat-rate Free: $0/mes** (con límites, ver README) | 0 |
| S3 (frontend, KB) | | <0.1 |
| DynamoDB on-demand (snapshots cada 10 turnos) | | <0.5 |
| CloudWatch Logs (retención 7 días) | 0.50 USD/GB ingerido; poco volumen | ~0.5–1 |
| ECR (1 imagen, <1 GB) | 0.10 USD/GB-mes | ~0.1 |
| SSM Parameter Store (estándar), IAM, Budgets | | 0 |
| **Total estimado** | | **~43–49** |

Si la tarea se subiera a 1 vCPU / 2 GB (ARM) serían ~+14 USD/mes (ver README, sección Latencia).

## Gasto real durante el evento
_(Completar con Cost Explorer: agrupar por servicio, filtro "Tipo de cargo" sin Credit/Refund, igual que el Budget.)_

| Fecha | Servicio | USD |
|---|---|---|
| | | |
| **Total real** | | |

## Cómo se redujo el costo
- Sin NAT Gateway (~32 USD/mes): la tarea está en subred pública con IP pública y un security group que solo acepta del ALB.
- Sin Redis/ElastiCache, sin API Gateway/AppSync, sin Secrets Manager ni Amazon Location Service.
- Una sola tarea ARM (Graviton). CloudFront en plan Free.
- Logs a 7 días; DynamoDB on-demand; mapa con Leaflet y teselas abiertas.

## Cierre del evento (para no seguir pagando)
El ALB y Fargate cobran **por hora** aunque nadie los use. Al terminar: bajar el servicio a 0 tareas (o borrarlo), borrar el ALB, la distribución de CloudFront, eliminar las access keys y revisar que no exista un NAT Gateway.
