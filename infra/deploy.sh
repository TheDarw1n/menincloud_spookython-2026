#!/usr/bin/env bash
# Uso: ./infra/deploy.sh [backend|frontend|prueba|all]   (por defecto: all)
# Requiere credenciales de CLI de TU usuario IAM (ver README > Despliegue). Nunca las subas al repo.
# Variables opcionales: PLATFORM=linux/amd64 (si cambias la task definition a X86_64), BUCKET, DIST_ID
set -euo pipefail

REGION=us-east-1
BUCKET=${BUCKET:-frontend-manta}
DIST_ID=${DIST_ID:-E1PWAP92TTAQQH}
CLUSTER=${CLUSTER:-manta}
SERVICE=${SERVICE:-manta-api}
PLATFORM=${PLATFORM:-linux/arm64}
ACCOUNT_ID=${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}
REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
REPO="$REGISTRY/manta-zombie"
QUE=${1:-all}

backend() {
  if [[ "$PLATFORM" == "linux/arm64" && "$(uname -m)" =~ ^(x86_64|amd64)$ ]]; then
    echo "AVISO: construyes ARM64 desde x86 con emulacion (QEMU): sera lento. Alternativa: PLATFORM=linux/amd64"
    echo "       y cambiar runtimePlatform de la task definition a X86_64."
  fi
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
  SHA=$(git rev-parse --short HEAD 2>/dev/null || echo manual)
  docker buildx build --platform "$PLATFORM" -t "$REPO:latest" -t "$REPO:$SHA" --push .
  # Estado en memoria => 1 sola tarea: nunca dos a la vez (min 0 % / max 100 %; hay ~1 min de corte)
  aws ecs update-service --region "$REGION" --cluster "$CLUSTER" --service "$SERVICE" \
    --force-new-deployment --deployment-configuration "minimumHealthyPercent=0,maximumPercent=100" >/dev/null
  echo "Esperando a que el servicio se estabilice..."
  aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER" --services "$SERVICE"
  echo "Backend desplegado: $REPO:$SHA"
}

frontend() {
  aws s3 sync frontend/ "s3://$BUCKET" --delete
  aws s3 cp data/manta_graph.json "s3://$BUCKET/manta_graph.json"   # el mapa lo lee como archivo estatico
  aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null
  echo "Frontend publicado en S3 + invalidacion de CloudFront enviada"
}

prueba() {
  # Humo + latencia contra la URL publica (CloudFront -> ALB -> tarea). Desde CloudShell en
  # us-east-1 mide el servidor sin la red de Ecuador. Requiere API_KEY (la del jurado, no la de operador).
  URL=${URL:-https://d160b5kavxovby.cloudfront.net}
  curl -sf "$URL/salud" >/dev/null && echo "salud OK" || { echo "FALLA: $URL/salud"; exit 1; }
  curl -sf "$URL/manta_graph.json" -o /dev/null && echo "grafo OK" || echo "FALLA: grafo en S3"
  curl -sf -X POST "$URL/paso" -H "x-api-key: ${API_KEY:?exporta API_KEY}" -H "content-type: application/json"     -d '{"sobrevivienteId":"S-0001","nodoActual":"N-0001","turno":1}' && echo
  python3 -m src.simulator.latency "$URL" "$API_KEY" --niveles 20,80,200 --turnos 5 --intervalo 2
}

case "$QUE" in
  backend)  backend ;;
  frontend) frontend ;;
  prueba)   prueba ;;
  all)      backend; frontend ;;
  *) echo "Uso: $0 [backend|frontend|prueba|all]"; exit 1 ;;
esac
