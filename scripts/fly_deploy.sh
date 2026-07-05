#!/usr/bin/env bash
# Full Fly.io deploy for Dental MVP. Local Docker is NOT touched.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FLY="${FLYCTL:-$HOME/.fly/bin/flyctl}"
REGION="${FLY_REGION:-ams}"
ORG="${FLY_ORG:-ingbaga}"

APP_NATS=dental-mvp-nats
APP_REDIS=dental-mvp-redis
APP_CRM=dental-mvp-crm
APP_CORE=dental-mvp-core
APP_AI=dental-mvp-ai
APP_BOT=dental-mvp-bot
APP_WORKER=dental-mvp-worker
APP_ADMIN=dental-mvp-admin
APP_DOCS=dental-mvp-docs
PG_NAME=dental-mvp-db

log() { echo "[fly-deploy] $*"; }

ensure_app() {
  local app="$1"
  if ! "$FLY" apps list --json | python3 -c "import json,sys; apps={a['Name'] for a in json.load(sys.stdin)}; sys.exit(0 if '$app' in apps else 1)" 2>/dev/null; then
    log "Creating app $app"
    "$FLY" apps create "$app" --org "$ORG" || true
  fi
}

to_sqlalchemy_url() {
  local url="$1"
  url="${url/postgres:\/\//postgresql+psycopg:\/\/}"
  url="${url/postgresql:\/\//postgresql+psycopg:\/\/}"
  echo "$url"
}

load_env() {
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
}

provision_postgres() {
  if ! "$FLY" postgres list --json | python3 -c "import json,sys; names={c['Name'] for c in json.load(sys.stdin)}; sys.exit(0 if '$PG_NAME' in names else 1)" 2>/dev/null; then
    log "Creating Postgres cluster $PG_NAME"
    "$FLY" postgres create \
      --name "$PG_NAME" \
      --region "$REGION" \
      --initial-cluster-size 1 \
      --vm-size shared-cpu-1x \
      --volume-size 3 \
      --org "$ORG"
  fi
  if ! "$FLY" secrets list -a "$APP_CORE" 2>/dev/null | grep -q 'DATABASE_URL'; then
    log "Attaching Postgres to $APP_CORE"
    "$FLY" postgres attach "$PG_NAME" --app "$APP_CORE" --yes || true
  else
    log "Postgres already attached to $APP_CORE"
  fi
}

deploy_app() {
  local dir="$1"
  log "Deploying $(basename "$dir")"
  (cd "$ROOT" && "$FLY" deploy --config "fly/$dir/fly.toml" --ha=false --yes)
}

deploy_infra() {
  local dir="$1"
  log "Deploying infra $(basename "$dir")"
  (cd "$ROOT/fly/$dir" && "$FLY" deploy --ha=false --yes)
}

main() {
  cd "$ROOT"
  load_env

  log "Fly auth: $("$FLY" auth whoami)"
  log "Region: $REGION | Org: $ORG"

  for app in "$APP_NATS" "$APP_REDIS" "$APP_CRM" "$APP_CORE" "$APP_AI" "$APP_BOT" "$APP_WORKER" "$APP_ADMIN" "$APP_DOCS"; do
    ensure_app "$app"
  done

  provision_postgres

  REDIS_URL="redis://${APP_REDIS}.internal:6379/0"
  NATS_URL="nats://${APP_NATS}.internal:4222"
  CRM_URL="https://${APP_CRM}.fly.dev"
  CORE_URL="https://${APP_CORE}.fly.dev"
  AI_URL="https://${APP_AI}.fly.dev"
  BOT_PUBLIC="https://${APP_BOT}.fly.dev"
  ADMIN_PUBLIC="https://${APP_ADMIN}.fly.dev"
  DOCS_PUBLIC="https://${APP_DOCS}.fly.dev"
  WEBHOOK_URL="${BOT_PUBLIC}/api/telegram/webhook"

  log "Internal URLs: CORE=$CORE_URL AI=$AI_URL CRM=$CRM_URL NATS=$NATS_URL"

  # NATS + Redis volumes + deploy
  (cd "$ROOT/fly/nats" && "$FLY" volumes create nats_data --region "$REGION" --size 1 --yes 2>/dev/null || true)
  (cd "$ROOT/fly/redis" && "$FLY" volumes create redis_data --region "$REGION" --size 1 --yes 2>/dev/null || true)
  deploy_infra nats
  deploy_infra redis
  deploy_app crm

  "$FLY" secrets set -a "$APP_CRM" \
    INTERNAL_SERVICE_TOKEN="$INTERNAL_SERVICE_TOKEN" \
    CRM_MOCK_FAILURE_RATE="${CRM_MOCK_FAILURE_RATE:-0}" \
    LOG_LEVEL="${LOG_LEVEL:-INFO}"

  # Core gets DATABASE_URL from postgres attach; set the rest
  DB_URL="$("$FLY" secrets list -a "$APP_CORE" 2>/dev/null | awk '/DATABASE_URL/{print}' || true)"
  if [ -z "$DB_URL" ]; then
    log "Waiting for DATABASE_URL from postgres attach..."
    sleep 3
  fi

  "$FLY" secrets set -a "$APP_CORE" \
    CORE_API_URL="$CORE_URL" \
    REDIS_URL="$REDIS_URL" \
    NATS_URL="$NATS_URL" \
    CRM_MOCK_URL="$CRM_URL" \
    INTERNAL_SERVICE_TOKEN="$INTERNAL_SERVICE_TOKEN" \
    AI_ORCHESTRATOR_URL="$AI_URL" \
    BOT_GATEWAY_URL="$BOT_PUBLIC" \
    ADMIN_TOKEN="$ADMIN_TOKEN" \
    AI_MODE="${AI_MODE:-rules}" \
    CLINIC_PHONE="${CLINIC_PHONE:-+79990000000}" \
    STAFF_GROUP_CHAT_ID="${STAFF_GROUP_CHAT_ID:-}" \
    DOCTOR_TELEGRAM_IDS="${DOCTOR_TELEGRAM_IDS:-}" \
    STAFF_TELEGRAM_IDS="${STAFF_TELEGRAM_IDS:-}" \
    DEBUG_API_ENABLED="${DEBUG_API_ENABLED:-false}" \
    DEBUG_API_TOKEN="${DEBUG_API_TOKEN:-$ADMIN_TOKEN}" \
    LOG_LEVEL="${LOG_LEVEL:-INFO}"

  # Convert DATABASE_URL for SQLAlchemy before first core deploy
  if "$FLY" secrets list -a "$APP_CORE" 2>/dev/null | grep -q 'DATABASE_URL'; then
    RAW_DB="$("$FLY" ssh console -a "$APP_CORE" -C 'printenv DATABASE_URL' 2>/dev/null || true)"
    if echo "$RAW_DB" | grep -q '^postgres://'; then
      FIXED_DB="$(echo "$RAW_DB" | sed 's|^postgres://|postgresql+psycopg://|')"
      log "Setting SQLAlchemy DATABASE_URL"
      "$FLY" secrets set -a "$APP_CORE" DATABASE_URL="$FIXED_DB"
    fi
  fi

  deploy_app core

  # Re-check after deploy if still postgres://
  RAW_DB="$("$FLY" ssh console -a "$APP_CORE" -C 'printenv DATABASE_URL' 2>/dev/null || true)"
  if echo "$RAW_DB" | grep -q '^postgres://'; then
    FIXED_DB="$(echo "$RAW_DB" | sed 's|^postgres://|postgresql+psycopg://|')"
    log "Converting DATABASE_URL for SQLAlchemy (post-deploy)"
    "$FLY" secrets set -a "$APP_CORE" DATABASE_URL="$FIXED_DB"
    deploy_app core
  fi

  "$FLY" secrets set -a "$APP_AI" \
    CORE_API_URL="$CORE_URL" \
    NATS_URL="$NATS_URL" \
    INTERNAL_SERVICE_TOKEN="$INTERNAL_SERVICE_TOKEN" \
    AI_MODE="${AI_MODE:-rules}" \
    OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}" \
    OPENAI_MODEL="${OPENAI_MODEL:-gpt-4.1-mini}" \
    LOG_LEVEL="${LOG_LEVEL:-INFO}"

  deploy_app ai

  "$FLY" secrets set -a "$APP_BOT" \
    CORE_API_URL="$CORE_URL" \
    AI_ORCHESTRATOR_URL="$AI_URL" \
    REDIS_URL="$REDIS_URL" \
    INTERNAL_SERVICE_TOKEN="$INTERNAL_SERVICE_TOKEN" \
    TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    TELEGRAM_MODE=webhook \
    TELEGRAM_WEBHOOK_URL="$WEBHOOK_URL" \
    TELEGRAM_WEBHOOK_SECRET="$TELEGRAM_WEBHOOK_SECRET" \
    TELEGRAM_PROXY_URL="" \
    TELEGRAM_API_BASE="${TELEGRAM_API_BASE:-https://api.telegram.org}" \
    DEBUG_API_ENABLED="${DEBUG_API_ENABLED:-false}" \
    DEBUG_API_TOKEN="${DEBUG_API_TOKEN:-$ADMIN_TOKEN}" \
    LOG_LEVEL="${LOG_LEVEL:-INFO}"

  deploy_app bot

  "$FLY" secrets set -a "$APP_WORKER" \
    CORE_API_URL="$CORE_URL" \
    NATS_URL="$NATS_URL" \
    INTERNAL_SERVICE_TOKEN="$INTERNAL_SERVICE_TOKEN" \
    TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    TELEGRAM_PROXY_URL="" \
    TELEGRAM_API_BASE="${TELEGRAM_API_BASE:-https://api.telegram.org}" \
    STAFF_GROUP_CHAT_ID="${STAFF_GROUP_CHAT_ID:-}" \
    LOG_LEVEL="${LOG_LEVEL:-INFO}"

  deploy_app worker

  "$FLY" secrets set -a "$APP_ADMIN" \
    CORE_API_URL="$CORE_URL" \
    BOT_GATEWAY_URL="$BOT_PUBLIC" \
    AI_ORCHESTRATOR_URL="$AI_URL" \
    INTERNAL_SERVICE_TOKEN="$INTERNAL_SERVICE_TOKEN" \
    ADMIN_TOKEN="$ADMIN_TOKEN" \
    LOG_LEVEL="${LOG_LEVEL:-INFO}"

  deploy_app admin
  deploy_app docs

  log "Waiting for health checks..."
  sleep 15

  log "=== Fly.io deploy complete ==="
  log "Docs (mentor):  $DOCS_PUBLIC"
  log "Admin (mentor): $ADMIN_PUBLIC"
  log "Bot webhook:    $WEBHOOK_URL"
  log "Core health:    ${BOT_PUBLIC/https:\/\//https:\/\/}/../  -> curl $CORE_URL/health (internal only)"

  for url in "$DOCS_PUBLIC" "$ADMIN_PUBLIC/health" "$BOT_PUBLIC/health"; do
    code=$(curl -sf -o /dev/null -w "%{http_code}" "$url" || echo "fail")
    log "HTTP $code  $url"
  done

  cat > "$ROOT/.env.fly" <<EOF
# Auto-generated Fly.io URLs (do not commit)
FLY_DOCS_URL=$DOCS_PUBLIC
FLY_ADMIN_URL=$ADMIN_PUBLIC
FLY_BOT_URL=$BOT_PUBLIC
FLY_WEBHOOK_URL=$WEBHOOK_URL
FLY_CORE_INTERNAL=$CORE_URL
FLY_REGION=$REGION
EOF
  log "Wrote $ROOT/.env.fly"
}

main "$@"
