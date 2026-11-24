#!/bin/sh
# Teste de restauração do backup do Sistema de Estoque (roda na VM).
# Restaura um dump num banco TEMPORÁRIO (teste_restore), compara a contagem de
# linhas de todas as tabelas com a produção e apaga o temporário.
# A produção não é alterada.
#
# Uso:
#   sh deploy/estoque-teste-restore.sh                 # último dump da VM
#   sh deploy/estoque-teste-restore.sh /caminho/x.dump # dump específico
#   sh deploy/estoque-teste-restore.sh /tmp/x.dump --apagar-dump
#       (usado pelo script do PC: apaga o arquivo enviado no fim)
set -eu

DIR="${ESTOQUE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/estoque}"
DUMP="${1:-}"
APAGAR="${2:-}"

cd "$DIR"
if [ -z "$DUMP" ]; then
    DUMP="$(ls -t "$BACKUP_DIR"/estoque-*.dump 2>/dev/null | head -1 || true)"
    [ -n "$DUMP" ] || { echo "ERRO: nenhum dump em $BACKUP_DIR" >&2; exit 1; }
fi
[ -r "$DUMP" ] || { echo "ERRO: não consigo ler $DUMP" >&2; exit 1; }

TMPD="$(mktemp -d)"
limpar() {
    docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists teste_restore' >/dev/null 2>&1 || true
    rm -rf "$TMPD"
    if [ "$APAGAR" = "--apagar-dump" ]; then rm -f "$DUMP"; fi
}
trap limpar EXIT

q() {
    docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d \"$1\" -AtX -F'|' -c \"$2\""
}
COUNTS="select table_name, (xpath('/row/c/text()', query_to_xml('select count(*) as c from public.'||quote_ident(table_name), false, true, '')))[1]::text from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"
PROD_DB="$(docker compose exec -T db sh -c 'printf %s "$POSTGRES_DB"')"

echo "== dump: $DUMP ($(du -h "$DUMP" | cut -f1))"
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists teste_restore 2>/dev/null; createdb -U "$POSTGRES_USER" teste_restore'
docker compose exec -T db sh -c 'pg_restore --no-owner --exit-on-error -U "$POSTGRES_USER" -d teste_restore' < "$DUMP"
echo "== restauração: ok"

q "$PROD_DB" "$COUNTS" > "$TMPD/prod.txt"
q teste_restore "$COUNTS" > "$TMPD/rest.txt"
echo "== tabelas: $(wc -l < "$TMPD/rest.txt") restauradas / $(wc -l < "$TMPD/prod.txt") na produção"
echo "== linhas por tabela (restaurado, só as não vazias):"
grep -v '|0$' "$TMPD/rest.txt" || true
echo "== última migration restaurada: $(q teste_restore "select name from django_migrations where app='core' order by id desc limit 1")"
if diff "$TMPD/prod.txt" "$TMPD/rest.txt" > "$TMPD/diff.txt"; then
    echo "== comparação: idêntico à produção"
else
    echo "== comparação: diferenças (normal se o sistema foi usado depois do backup):"
    cat "$TMPD/diff.txt"
fi
echo "== TESTE OK (banco temporário removido)"
