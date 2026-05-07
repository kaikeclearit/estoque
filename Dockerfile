FROM python:3.12-slim

# Define a pasta raiz do container
WORKDIR /app_root

# Instala as dependências do sistema
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copia os requisitos e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do projeto
COPY . .

# MUDA A PASTA DE TRABALHO PARA ONDE O MANAGE.PY REALMENTE ESTÁ!
WORKDIR /app_root/app

# Expõe a porta 8000
EXPOSE 8000

# Agora o manage.py está na mesma pasta que o comando
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]