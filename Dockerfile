# syntax=docker/dockerfile:1
# Imagem de produção do sistema de estoque (Django + Gunicorn + WhiteNoise).
# Build:  docker build -t kaikeclear/estoque-app:<tag> .

ARG PYTHON_IMAGE=python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

# ---------------------------------------------------------------------------
# Stage 1: dependências Python em um virtualenv isolado
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
# psycopg2-binary já traz a libpq: não precisa de gcc/libpq-dev.
RUN pip install -r /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: imagem final, sem ferramentas de build
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=setup.settings \
    WEB_CONCURRENCY=3

# Usuário não-root com UID fixo (usado no securityContext do Kubernetes).
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app_root
# O .dockerignore impede que .env, planilhas, segredos, .git, sqlite etc.
# entrem na imagem.
COPY . .

WORKDIR /app_root/app

# collectstatic no build: STATIC_ROOT = /app_root/app/static, servido pelo
# WhiteNoise. settings.py importa sem variáveis de ambiente (chave de dev só
# para este passo; o entrypoint bloqueia a chave de dev em runtime).
RUN sed -i 's/\r$//' entrypoint.sh \
    && python manage.py collectstatic --noinput \
    && chmod 0755 entrypoint.sh

USER 10001:10001

EXPOSE 8000

# Usado pelo Docker/Compose (no Kubernetes valem as probes do Deployment).
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8000), 2)"]

ENTRYPOINT ["/app_root/app/entrypoint.sh"]
CMD ["gunicorn", "setup.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "gthread", "--threads", "2", \
     "--worker-tmp-dir", "/dev/shm", \
     "--timeout", "60", "--graceful-timeout", "30", \
     "--access-logfile", "-", "--error-logfile", "-"]
