#!/usr/bin/env bash
# Uso: ./infra/deploy.sh [backend|frontend|taskdef|prueba|all]   (por defecto: all)
# Requiere credenciales de CLI de TU usuario IAM (ver README > Despliegue). Nunca las subas al repo.
# Variables opcionales: PLATFORM=linux/amd64 (si cambias la task definition a X86_64), BUCKET, DIST_ID,
# TASK_FAMILY
set -euo pipefail
# En Git Bash (Windows) los argumentos que empiezan con "/" ("/*" de la invalidacion, "/manta/...")
# se convierten en rutas de Windows y rompen los comandos; en Linux y CloudShell no tiene efecto.
export MSYS_NO_PATHCONV=1

REGION=us-east-1
BUCKET=${BUCKET:-frontend-manta}
DIST_ID=${DIST_ID:-E1PWAP92TTAQQH}
CLUSTER=${CLUSTER:-manta}
SERVICE=${SERVICE:-manta-api}
TASK_FAMILY=${TASK_FAMILY:-manta-api}
PLATFORM=${PLATFORM:-linux/arm64}
QUE=${1:-all}

cuenta() {  # solo backend y taskdef necesitan la cuenta: prueba funciona sin credenciales de AWS
  ACCOUNT_ID=${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text | tr -d '\r')}  # aws.exe en Windows termina en CRLF
  REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
  REPO="$REGISTRY/manta-zombie"
}

backend() {
  cuenta
  if [[ "$PLATFORM" == "linux/arm64" && "$(uname -m)" =~ ^(x86_64|amd64)$ ]]; then
    echo "AVISO: construyes ARM64 desde x86 con emulacion (QEMU): sera lento. Alternativa: PLATFORM=linux/amd64"
    echo "       y cambiar runtimePlatform de la task definition a X86_64."
  fi
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
  SHA=$(git rev-parse --short HEAD 2>/dev/null || echo manual)
  docker buildx build --platform "$PLATFORM" -t "$REPO:latest" -t "$REPO:$SHA" --push .
  # Estado en memoria => 1 sola tarea: nunca dos a la vez (min 0 % / max 100 %; hay ~1 min de corte).
  # --task-definition con solo la familia = su ultima revision ACTIVE (la que registra `taskdef`).
  aws ecs update-service --region "$REGION" --cluster "$CLUSTER" --service "$SERVICE" \
    --task-definition "$TASK_FAMILY" --force-new-deployment \
    --deployment-configuration "minimumHealthyPercent=0,maximumPercent=100" >/dev/null
  echo "Esperando a que el servicio se estabilice..."
  aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE"
  echo "Backend desplegado: $REPO:$SHA"
}

frontend() {
  # no-cache: el navegador revalida cada archivo del mapa (304 si no cambio), asi nunca mezcla
  # un index.html nuevo con un css o un js viejo
  aws s3 sync frontend/ "s3://$BUCKET" --delete --cache-control no-cache
  aws s3 cp data/manta_graph.json "s3://$BUCKET/manta_graph.json"   # el mapa lo lee como archivo estatico
  aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null
  echo "Frontend publicado en S3 + invalidacion de CloudFront enviada"
}

taskdef() {
  # infra/task-definition.json se RECONSTRUYO a partir de la configuracion descrita (no se exporto de
  # la consola): comparala antes con la revision actual (ECS > Task definitions > manta-api > JSON).
  cuenta
  # archivo temporal con ruta relativa: aws.exe (Git Bash en Windows) no encuentra el /tmp de mktemp
  local tmp="infra/.taskdef-$$.json"
  trap 'rm -f "$tmp"' EXIT
  sed "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" infra/task-definition.json > "$tmp"
  aws ecs register-task-definition --region "$REGION" --cli-input-json "file://$tmp" \
    --query 'taskDefinition.taskDefinitionArn' --output text
  rm -f "$tmp"
}

prueba() {
  # Humo + latencia contra la URL publica (CloudFront -> ALB -> tarea). Desde CloudShell en
  # us-east-1 mide el servidor sin la red de Ecuador. Requiere API_KEY (la del jurado, no la de operador).
  URL=${URL:-https://d160b5kavxovby.cloudfront.net}
  curl -sf "$URL/salud" >/dev/null && echo "salud OK" || { echo "FALLA: $URL/salud"; exit 1; }
  # el grafo de S3 debe ser el de Manta (307 nodos), no el de prueba del prototipo (20)
  curl -sf "$URL/manta_graph.json" | python3 -c "import json,sys; n=len(json.load(sys.stdin)['nodos']); print('grafo OK:', n, 'nodos') if n > 100 else print('FALLA: el grafo publicado tiene', n, 'nodos: corre ./infra/deploy.sh frontend')" || echo "FALLA: grafo en S3"
  curl -sf -X POST "$URL/paso" -H "x-api-key: ${API_KEY:?exporta API_KEY}" -H "content-type: application/json"     -d '{"sobrevivienteId":"S-0001","nodoActual":"N-0001","turno":1}' && echo
  python3 -m src.simulator.latency "$URL" "$API_KEY" --niveles 20,80,200 --turnos 5 --intervalo 2
}

case "$QUE" in
  backend)  backend ;;
  frontend) frontend ;;
  taskdef)  taskdef ;;
  prueba)   prueba ;;
  all)      backend; frontend ;;
  *) echo "Uso: $0 [backend|frontend|taskdef|prueba|all]"; exit 1 ;;
esac
