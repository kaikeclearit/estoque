# Dockerfile
FROM python:3.11-slim

# Evita que o Python gere arquivos .pyc e bufferize logs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instala dependências do sistema necessárias para o Postgres e compiladores
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


RUN pip install --upgrade pip


# Instala as dependências Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia o projeto para dentro do container
COPY ./app /app

# (Opcional) Cria um usuário não-root por segurança
# RUN useradd -m myuser
# USER myuser

# Comando padrão (será sobrescrito pelo docker-compose, mas bom ter)
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]