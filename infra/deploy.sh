#!/usr/bin/env bash
# Uso: ./infra/deploy.sh [backend|frontend|all]   (por defecto: all)
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

case "$QUE" in
  backend)  backend ;;
  frontend) frontend ;;
  all)      backend; frontend ;;
  *) echo "Uso: $0 [backend|frontend|all]"; exit 1 ;;
esac
