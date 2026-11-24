#!/bin/sh
# Vigia do Sistema de Estoque na VM (rodado pelo estoque-watchdog.timer).
# - Sobe de novo web/db se estiverem parados ou removidos.
# - Reinicia o web se o healthcheck do Docker marcar "unhealthy"
#   (o Docker sozinho NÃO reinicia container unhealthy).
# Não roda migrations nem build: só garante que o que já existe está no ar.
set -u
DIR="${ESTOQUE_DIR:-/opt/estoque}"
cd "$DIR" || { echo "watchdog: pasta $DIR não existe" >&2; exit 1; }

docker compose up -d --no-deps --no-build db web

WEB_ID="$(docker compose ps -q web)"
if [ -n "$WEB_ID" ]; then
    STATUS="$(docker inspect -f '{{.State.Health.Status}}' "$WEB_ID" 2>/dev/null || echo unknown)"
    if [ "$STATUS" = "unhealthy" ]; then
        echo "watchdog: web unhealthy, reiniciando"
        docker compose restart web
    fi
fi
