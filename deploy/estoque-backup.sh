#!/bin/sh
# Backup do banco do Sistema de Estoque (rodado pelo estoque-backup.timer).
# - pg_dump em formato custom (-Fc), validado com pg_restore --list antes de
#   ser aceito; dump com problema nunca substitui os bons.
# - Mantém BACKUP_KEEP_DAYS dias (padrão 30).
# - Se BACKUP_COPY_TO estiver definido (pasta montada de outro servidor/NAS),
#   copia o dump para lá também.
# - Se BACKUP_OWNER estiver definido (usuário SSH da VM), os dumps ficam
#   legíveis só por ele, para um PC/servidor externo puxar via scp.
# Sai com erro se qualquer etapa falhar => aparece em "systemctl --failed".
set -eu
umask 077

DIR="${ESTOQUE_DIR:-/opt/estoque}"
DEST="${BACKUP_DIR:-/var/backups/estoque}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
COPY_TO="${BACKUP_COPY_TO:-}"
OWNER="${BACKUP_OWNER:-}"

cd "$DIR"
mkdir -p "$DEST"

TS="$(date +%F_%H%M)"
FINAL="$DEST/estoque-$TS.dump"
TMP="$DEST/.estoque-$TS.dump.tmp"
trap 'rm -f "$TMP"' EXIT

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$TMP"

if [ ! -s "$TMP" ]; then
    echo "backup: dump vazio" >&2
    exit 1
fi
# Confere se o arquivo é um dump legível (catálogo completo).
docker compose exec -T db pg_restore --list < "$TMP" > /dev/null

mv "$TMP" "$FINAL"
if [ -n "$OWNER" ]; then
    chown "$OWNER" "$DEST" "$DEST"/estoque-*.dump
fi
echo "backup: ok $FINAL ($(du -h "$FINAL" | cut -f1))"

find "$DEST" -name 'estoque-*.dump' -mtime +"$KEEP_DAYS" -delete

if [ -n "$COPY_TO" ]; then
    cp "$FINAL" "$COPY_TO"/
    find "$COPY_TO" -name 'estoque-*.dump' -mtime +"$KEEP_DAYS" -delete
    echo "backup: copiado para $COPY_TO"
fi
