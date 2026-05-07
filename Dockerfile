# Usa uma imagem oficial do Python super leve
FROM python:3.12-slim

# Define a pasta de trabalho dentro do container
WORKDIR /app

# Instala as dependências do sistema necessárias para o banco de dados (opcional, mas recomendado)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos e instala as bibliotecas Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o resto do código da sua máquina para dentro do container
COPY . .

# Expõe a porta 8000 (padrão do Django)
EXPOSE 8000

# Comando que o container vai rodar quando ligar
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]