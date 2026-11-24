#!/bin/sh
# Entrypoint da imagem de produção.
# Falha cedo se a configuração mínima de produção estiver ausente, para que
# o settings.py possa continuar importando sem variáveis de ambiente (dev e
# collectstatic no build).
set -eu

if [ "${DJANGO_ALLOW_INSECURE:-0}" != "1" ]; then
    if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
        echo "ERRO: DJANGO_SECRET_KEY não definida (configure o Secret supply-secrets)." >&2
        exit 1
    fi
    if [ "${#DJANGO_SECRET_KEY}" -lt 50 ]; then
        echo "ERRO: DJANGO_SECRET_KEY muito curta (mínimo 50 caracteres)." >&2
        exit 1
    fi
    case "$(printf '%s' "${DEBUG:-false}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on)
            echo "ERRO: DEBUG ligado em produção. Use DJANGO_ALLOW_INSECURE=1 apenas em dev." >&2
            exit 1
            ;;
    esac
    for var in DATABASE_NAME DATABASE_USER DATABASE_PASSWORD DATABASE_HOST; do
        eval "val=\${$var:-}"
        if [ -z "$val" ]; then
            echo "ERRO: variável $var não definida." >&2
            exit 1
        fi
    done
fi

exec "$@"
