# 🚀 Guia de Deployment

Guia completo para deploy do Sistema de Estoque ClearIT em ambiente de produção usando Docker.

---

## 📋 Pré-requisitos

### Servidor
- **SO:** Ubuntu 20.04+ ou similar
- **RAM:** Mínimo 2GB (recomendado 4GB)
- **Disco:** 20GB disponíveis
- **Portas:** 80 (HTTP) e 443 (HTTPS, se usar SSL)

### Software
- Docker 20.10+
- Docker Compose 1.29+
- Git

### Instalação do Docker (Ubuntu)

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependências
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Adicionar repositório Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verificar instalação
docker --version
docker compose version

# Adicionar usuário ao grupo docker (logout/login necessário)
sudo usermod -aG docker $USER
```

---

## 🏗️ Arquitetura de Deploy

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                   Port 80/443
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                    Nginx Container                          │
│  • Reverse Proxy                                            │
│  • Static Files Serving                                     │
│  • Media Files Serving                                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                   Port 8000
                        │
┌───────────────────────▼─────────────────────────────────────┐
│              Django + Gunicorn Container                    │
│  • Application Logic                                        │
│  • REST API                                                 │
│  • Authentication                                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                   Port 5432
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                PostgreSQL Container                         │
│  • Database                                                 │
│  • Persistent Volume                                        │
└─────────────────────────────────────────────────────────────┘

Volumes:
  • postgres_data → /var/lib/postgresql/data
  • static_volume → /app/static
  • media_volume → /app/media
```

---

## 📂 Estrutura de Arquivos no Servidor

```
/root/estoque-prod/
├── .env                        # Variáveis de ambiente (NÃO commitar!)
├── docker-compose.yml          # Orquestração
├── Dockerfile                  # Build da app Django
├── requirements.txt            # Dependências Python
├── app/                        # Código Django
│   ├── manage.py
│   ├── setup/
│   └── core/
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
└── volumes/                    # Criado pelo Docker
    ├── postgres_data/
    ├── static/
    └── media/
```

---

## ⚙️ Configuração do Ambiente

### 1. Clonar Repositório

```bash
cd /root
git clone https://github.com/sua-empresa/estoque-prod.git
cd estoque-prod
```

### 2. Criar Arquivo `.env`

```bash
nano .env
```

**Conteúdo do `.env`:**

```bash
# === DJANGO SETTINGS ===
SECRET_KEY=sua-chave-super-secreta-aqui-min-50-caracteres
DEBUG=False
ALLOWED_HOSTS=estoque.clearit.com,www.estoque.clearit.com,localhost

# === DATABASE ===
POSTGRES_DB=estoque_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=SenhaSuperSegura123!@#
DATABASE_URL=postgresql://postgres:SenhaSuperSegura123!@#@db:5432/estoque_db

# === MICROSOFT SSO ===
# Obter em: https://portal.azure.com → App Registrations
MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MICROSOFT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MICROSOFT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Redirect URI deve ser: https://seudominio.com/accounts/microsoft/login/callback/

# === WEBHOOK INTEGRATION ===
# Obter em: https://make.com → Webhook
RESERVATION_WEBHOOK_URL=https://hook.us1.make.com/xxxxxxxxxxxxxxxxxxxxxxxxx
SITE_URL=https://estoque.clearit.com

# === EMAIL (Opcional, se não usar webhook) ===
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-app

# === SECURITY ===
CSRF_TRUSTED_ORIGINS=https://estoque.clearit.com,https://www.estoque.clearit.com
```

**Proteção do arquivo:**
```bash
chmod 600 .env
```

### 3. Configurar Microsoft Azure AD

#### 3.1. Criar App Registration
1. Acesse https://portal.azure.com
2. Azure Active Directory → App registrations → New registration
3. Nome: "Sistema Estoque ClearIT"
4. Redirect URI: `https://estoque.clearit.com/accounts/microsoft/login/callback/`

#### 3.2. Obter Credenciais
- **Client ID:** Na página Overview do app
- **Tenant ID:** Na página Overview do app
- **Client Secret:** Certificates & secrets → New client secret

#### 3.3. Configurar Permissões
- Microsoft Graph → User.Read (Delegated)
- Conceder admin consent

### 4. Configurar Webhook no Make.com

1. Criar novo Scenario no Make.com
2. Adicionar trigger "Webhook"
3. Copiar URL do webhook
4. Adicionar módulos:
   - **Gmail:** Send an Email
   - **Template do Email:** Incluir botões "Confirmar" e "Cancelar"

**Exemplo de Template:**
```html
<h2>🔔 Nova Reserva de Material</h2>

<p>Olá {{ to_name }},</p>

<p>Foi criada uma reserva de material:</p>

<ul>
  <li><strong>Produto:</strong> {{ product_name }}</li>
  <li><strong>Quantidade:</strong> {{ quantity }}</li>
  <li><strong>Local:</strong> {{ location }}</li>
  <li><strong>Cliente:</strong> {{ client_name }}</li>
  <li><strong>Data Prevista:</strong> {{ scheduled_date }}</li>
</ul>

<p>Por favor, confirme a retirada ou cancele caso não utilize:</p>

<table style="margin: 20px 0;">
  <tr>
    <td style="padding: 10px;">
      <a href="{{ confirm_url }}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
        ✅ Confirmar Retirada
      </a>
    </td>
    <td style="padding: 10px;">
      <a href="{{ cancel_url }}" style="background: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
        ❌ Cancelar Reserva
      </a>
    </td>
  </tr>
</table>

<p><small>Este link expira em {{ expires_days }} dias.</small></p>
```

---

## 🐳 Deploy com Docker

### 1. Build das Imagens

```bash
cd /root/estoque-prod
docker compose build
```

**Saída esperada:**
```
[+] Building 45.3s (12/12) FINISHED
 => [web internal] load build definition from Dockerfile
 => [nginx internal] load build definition from dockerfile
...
```

### 2. Iniciar Banco de Dados

```bash
docker compose up -d db
```

**Aguardar inicialização:**
```bash
docker compose logs -f db
# Aguardar mensagem: "database system is ready to accept connections"
# Ctrl+C para sair
```

### 3. Executar Migrações

```bash
docker compose run --rm web python manage.py migrate
```

**Saída esperada:**
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, core, sessions, sites, socialaccount, account
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
```

### 4. Criar Superusuário

```bash
docker compose run --rm web python manage.py createsuperuser
```

**Prompts:**
```
Username: admin
Email: admin@clearit.com
Password: 
Password (again):
Superuser created successfully.
```

### 5. Coletar Arquivos Estáticos

```bash
docker compose run --rm web python manage.py collectstatic --noinput
```

### 6. Subir Todos os Serviços

```bash
docker compose up -d
```

**Verificar status:**
```bash
docker compose ps
```

**Saída esperada:**
```
NAME                   SERVICE   STATUS    PORTS
estoque-prod-db-1      db        running   5432/tcp
estoque-prod-web-1     web       running   8000/tcp
estoque-prod-nginx-1   nginx     running   0.0.0.0:80->80/tcp
```

### 7. Verificar Logs

```bash
# Todos os containers
docker compose logs -f

# Apenas Django
docker compose logs -f web

# Apenas Nginx
docker compose logs -f nginx
```

---

## 🔧 Configurações Adicionais

### Nginx com SSL (HTTPS)

#### 1. Instalar Certbot

```bash
sudo apt install certbot python3-certbot-nginx -y
```

#### 2. Obter Certificado

```bash
sudo certbot --nginx -d estoque.clearit.com
```

#### 3. Atualizar `nginx.conf`

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name estoque.clearit.com;

    ssl_certificate /etc/letsencrypt/live/estoque.clearit.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/estoque.clearit.com/privkey.pem;

    # Redirecionar HTTP → HTTPS
    if ($scheme != "https") {
        return 301 https://$host$request_uri;
    }

    # ... resto da config
}
```

#### 4. Renovação Automática

```bash
sudo systemctl status certbot.timer
```

### Backup Automático do Banco

**Script de Backup:**

```bash
#!/bin/bash
# /root/backup-db.sh

BACKUP_DIR=/root/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME=estoque_backup_$TIMESTAMP.sql

mkdir -p $BACKUP_DIR

docker compose exec -T db pg_dump -U postgres estoque_db > $BACKUP_DIR/$FILENAME

# Manter apenas últimos 7 dias
find $BACKUP_DIR -name "estoque_backup_*.sql" -mtime +7 -delete

echo "Backup criado: $FILENAME"
```

**Tornar executável:**
```bash
chmod +x /root/backup-db.sh
```

**Agendar no Cron (diário às 2h):**
```bash
crontab -e
```

Adicionar:
```
0 2 * * * /root/backup-db.sh >> /var/log/backup-db.log 2>&1
```

### Monitoramento de Logs

**Criar serviço de monitoramento:**

```bash
# /root/monitor-logs.sh
#!/bin/bash

docker compose logs --tail=50 -f web | grep -E "(ERROR|CRITICAL|Exception)"
```

---

## 🔄 Comandos Úteis

### Gerenciar Containers

```bash
# Reiniciar todos os serviços
docker compose restart

# Parar todos os serviços
docker compose stop

# Parar e remover containers
docker compose down

# Parar, remover E deletar volumes (CUIDADO!)
docker compose down -v
```

### Acessar Shell do Container

```bash
# Shell do Django
docker compose exec web bash

# Shell do PostgreSQL
docker compose exec db psql -U postgres -d estoque_db
```

### Executar Comandos Django

```bash
# Criar migrações
docker compose run --rm web python manage.py makemigrations

# Aplicar migrações
docker compose run --rm web python manage.py migrate

# Shell Django
docker compose run --rm web python manage.py shell

# Criar usuário
docker compose run --rm web python manage.py createsuperuser
```

### Ver Estatísticas de Uso

```bash
docker stats
```

### Limpar Imagens Antigas

```bash
docker system prune -a
```

---

## 🐛 Troubleshooting

### Problema: Container não inicia

**Verificar logs:**
```bash
docker compose logs web
```

**Causas comuns:**
- Variáveis de ambiente faltando no `.env`
- Porta 80 já em uso
- Banco de dados não está pronto

**Solução:**
```bash
# Verificar variáveis
docker compose config

# Verificar portas
sudo netstat -tulpn | grep :80
```

### Problema: Erro de Migração

**Resetar banco (DESENVOLVIMENTO APENAS!):**
```bash
docker compose down -v
docker compose up -d db
docker compose run --rm web python manage.py migrate
```

### Problema: Static Files não carregam

**Reexecutar collectstatic:**
```bash
docker compose run --rm web python manage.py collectstatic --noinput
docker compose restart nginx
```

### Problema: Permissões de Volume

```bash
# Ajustar permissões
docker compose exec web chown -R www-data:www-data /app/media
docker compose exec web chown -R www-data:www-data /app/static
```

### Problema: Webhook não dispara

**Verificar:**
1. URL do webhook está correta no `.env`?
2. Servidor consegue acessar a internet?
3. Logs do Django:
   ```bash
   docker compose logs -f web | grep webhook
   ```

### Problema: Login Microsoft não funciona

**Checklist:**
1. Redirect URI no Azure AD está correto?
2. Client ID e Secret estão corretos?
3. SITE_URL no `.env` está correto?
4. HTTPS está configurado? (Microsoft exige HTTPS em prod)

---

## 📊 Monitoramento em Produção

### Logs Centralizados

**Configurar Syslog:**
```yaml
# docker-compose.yml
services:
  web:
    logging:
      driver: syslog
      options:
        syslog-address: "tcp://seu-servidor-log:514"
```

### Métricas com Prometheus

**Adicionar exporters:**
```yaml
services:
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter
    environment:
      DATA_SOURCE_NAME: "postgresql://postgres:senha@db:5432/estoque_db?sslmode=disable"
```

---

## 🔒 Segurança em Produção

### Checklist de Segurança

- [ ] `DEBUG=False` no `.env`
- [ ] `SECRET_KEY` forte e única
- [ ] HTTPS configurado (Certbot)
- [ ] Firewall ativo (UFW)
- [ ] Senhas fortes no banco
- [ ] Arquivo `.env` com permissões 600
- [ ] Backups automáticos configurados
- [ ] Logs de acesso monitorados
- [ ] Atualizações de segurança aplicadas

### Configurar Firewall

```bash
# Instalar UFW
sudo apt install ufw

# Permitir SSH
sudo ufw allow 22/tcp

# Permitir HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Ativar
sudo ufw enable

# Verificar status
sudo ufw status
```

---

## 📈 Escalabilidade

### Para alta carga:

1. **Separar Nginx em servidor próprio**
2. **Replicar containers Django:**
   ```yaml
   web:
     deploy:
       replicas: 3
   ```
3. **Usar RDS (AWS) ou Cloud SQL (GCP) para banco**
4. **Adicionar Redis para cache:**
   ```yaml
   redis:
     image: redis:7-alpine
   ```

---

## 📞 Suporte

Em caso de problemas em produção:

1. Verificar logs: `docker compose logs -f`
2. Verificar status: `docker compose ps`
3. Consultar documentação: `/docs`
4. Contatar equipe de infraestrutura

---

**Última atualização:** Março 2026  
**Versão:** 1.0.0