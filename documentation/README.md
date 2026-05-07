# 📦 Sistema de Gestão de Estoque - ClearIT

Sistema completo de gerenciamento de estoque multi-localidade desenvolvido em Django, com suporte a autenticação híbrida (local + Microsoft SSO), controle de movimentações e sistema de reservas via email.

---

## 🎯 Visão Geral

O **Sistema de Estoque ClearIT** é uma aplicação web corporativa que permite:

- ✅ Controle de estoque em múltiplas localidades (Manaus e São Paulo)
- ✅ Registro de entradas e saídas de materiais
- ✅ Sistema de reservas com confirmação por email
- ✅ Autenticação híbrida (senha local + Microsoft SSO)
- ✅ Controle de permissões por grupos (Gestores vs Usuários)
- ✅ Auditoria completa de movimentações
- ✅ Proteção contra race conditions em operações de estoque
- ✅ Dashboard com métricas em tempo real

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    NGINX (Reverse Proxy)                    │
│                         Porta 80                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Django + Gunicorn (Web App)                    │
│                      Porta 8000                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Views Layer                                        │    │
│  │  • products.py  • clients.py  • movements.py       │    │
│  │  • reservations.py  • api.py                       │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                             │
│  ┌────────────▼───────────────────────────────────────┐    │
│  │  Business Logic & Models                           │    │
│  │  • Product  • ProductStock  • StockEntry           │    │
│  │  • StockOut  • Client  • Employee  • Tokens        │    │
│  └────────────┬───────────────────────────────────────┘    │
│               │                                             │
│  ┌────────────▼───────────────────────────────────────┐    │
│  │  Services & Signals                                │    │
│  │  • webhook_service.py                              │    │
│  │  • signals.py (envio automático de emails)        │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   PostgreSQL 15                             │
│              Banco de Dados Principal                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Integrações Externas                       │
├─────────────────────────────────────────────────────────────┤
│  • Microsoft Azure AD (SSO)                                 │
│  • Make.com Webhook (envio de emails de reserva)           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Modelo de Dados

### Entidades Principais

#### 1. **Employee** (Usuário)
- Extensão do `AbstractUser` do Django
- Suporta login híbrido (local + Microsoft SSO)
- Campos: `microsoft_oid`, `login_type`, `department`

#### 2. **Product** (Produto)
- Dados cadastrais do produto
- Campos: `name`, `model`, `manufacturer`, `product_id`
- **Não contém quantidade** (quantidade está em ProductStock)

#### 3. **ProductStock** (Estoque por Local)
- Tabela pivô que relaciona Produto + Localização
- Campos: `product`, `location` (MAO/SP), `quantity`
- **Constraint:** `quantity >= 0` (não permite estoque negativo)

#### 4. **StockEntry** (Entrada de Material)
- Registra entradas no estoque
- Tipos: COMPRA, RETORNO, AJUSTE, DOACAO
- **Atualiza automaticamente** o ProductStock

#### 5. **StockOut** (Saída de Material)
- Registra saídas do estoque
- Tipos: SAIDA, RESERVA, EMPRESTIMO, DESCARTE
- **Valida disponibilidade** antes de salvar
- Suporta cancelamento (soft delete)

#### 6. **Client** (Cliente/Setor)
- Destinatário das saídas
- Campo único: `name`

#### 7. **ReservationToken** (Token de Confirmação)
- Gerado automaticamente para reservas
- Expira em 7 dias
- Ações: CONFIRMED ou CANCELLED

---

## 🔒 Sistema de Permissões

### Grupos de Usuários

| Grupo | Permissões | Identificação |
|-------|------------|---------------|
| **Gestores** | CRUD completo em produtos, clientes e movimentações | Identificados pelo `jobTitle` no Azure AD (Infraestrutura, Pós-Vendas, Projetos, Suporte, Qualidade) |
| **Usuários Padrão** | Apenas visualização | Demais usuários |

### Rotas Protegidas

```python
# Exemplo de proteção por permissão
path('produtos/novo/', 
     gestor_only('add_product')(products.product_create), 
     name='product_create')
```

---

## 🔄 Fluxos Principais

### 1. Entrada de Material

```
[Gestor acessa formulário] 
    → Preenche: Produto, Tipo, NF, Local, Quantidade
    → Sistema salva StockEntry
    → **Transação Atômica**: ProductStock.quantity += entrada.quantity
    → Registro auditado com timestamp e responsável
```

### 2. Saída de Material

```
[Gestor acessa formulário]
    → Preenche: Produto, Local, Cliente, Quantidade
    → Sistema valida: ProductStock.quantity >= saída.quantity
    → **select_for_update()**: Trava o registro durante a transação
    → Se OK: Reduz estoque e salva StockOut
    → Se NOK: Retorna erro "Estoque insuficiente"
```

### 3. Sistema de Reservas

```
[Gestor cria saída tipo "RESERVA"]
    → Sistema salva StockOut (baixa estoque imediatamente)
    → Signal dispara: cria ReservationToken
    → Webhook envia email via Make.com com 2 botões:
        • Confirmar Retirada → converte RESERVA em SAIDA
        • Cancelar → devolve estoque e marca como cancelada
    → Token expira em 7 dias
```

### 4. Cancelamento/Reversão de Saída

```
[Gestor acessa histórico]
    → Clica em "Reverter"
    → **Transação Atômica**: ProductStock.quantity += saída.quantity
    → StockOut marcada como is_cancelled=True
    → Registra quem cancelou e quando
```

---

## 🛡️ Proteções Implementadas

### Contra Race Conditions

```python
# Exemplo no save() do StockOut
with transaction.atomic():
    stock = ProductStock.objects.select_for_update().filter(
        product=self.product, 
        location=self.location
    ).first()
    
    if stock.quantity < self.quantity:
        raise ValueError("Estoque insuficiente!")
    
    stock.quantity -= self.quantity
    stock.save()
```

**Por que funciona?**
- `select_for_update()`: Trava o registro no banco até a transação terminar
- `transaction.atomic()`: Garante que tudo acontece ou nada acontece (rollback automático em erro)

### Validações de Negócio

1. **Estoque nunca fica negativo** (Constraint no banco)
2. **Reservas exigem data prevista** (Validação no form)
3. **Tokens expiram automaticamente** (7 dias)
4. **Movimentações não podem ser editadas** (apenas canceladas)

---

## 🚀 Como Executar

### Pré-requisitos

- Docker & Docker Compose
- Variáveis de ambiente configuradas (`.env`)

### Configuração do `.env`

```bash
# Django
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=False
ALLOWED_HOSTS=seudominio.com,localhost

# Database
POSTGRES_DB=estoque_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=sua-senha-segura

# Microsoft SSO
MICROSOFT_CLIENT_ID=seu-client-id
MICROSOFT_SECRET=seu-client-secret
MICROSOFT_TENANT_ID=seu-tenant-id

# Webhook para emails
RESERVATION_WEBHOOK_URL=https://hook.us1.make.com/seu-webhook
SITE_URL=https://seudominio.com
```

### Subir o Ambiente

```bash
# 1. Build das imagens
docker-compose build

# 2. Rodar migrações
docker-compose run web python manage.py migrate

# 3. Criar superusuário
docker-compose run web python manage.py createsuperuser

# 4. Coletar arquivos estáticos
docker-compose run web python manage.py collectstatic --noinput

# 5. Subir aplicação
docker-compose up -d
```

### Acessar a Aplicação

- **Web App:** http://localhost
- **Admin Django:** http://localhost/admin

---

## 📁 Estrutura de Arquivos

```
estoque-prod/
├── app/
│   ├── core/                      # App principal
│   │   ├── models.py              # Modelos de dados
│   │   ├── views/                 # Controllers
│   │   │   ├── products.py        # CRUD de produtos
│   │   │   ├── clients.py         # CRUD de clientes
│   │   │   ├── movements.py       # Entradas/Saídas
│   │   │   ├── reservations.py    # Confirmação de reservas
│   │   │   └── api.py             # Endpoints JSON
│   │   ├── forms.py               # Formulários
│   │   ├── admin.py               # Configuração do admin
│   │   ├── signals.py             # Eventos automáticos
│   │   ├── services/
│   │   │   └── webhook_service.py # Integração com Make.com
│   │   └── templates/             # HTML Templates
│   ├── setup/                     # Configurações Django
│   │   ├── settings.py            # Configuração principal
│   │   ├── urls.py                # Rotas principais
│   │   └── wsgi.py                # WSGI entry point
│   └── manage.py                  # CLI do Django
├── nginx/                         # Configuração Nginx
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml             # Orquestração de containers
├── Dockerfile                     # Build da app Django
└── requirements.txt               # Dependências Python
```

---

## 🔧 Tecnologias Utilizadas

| Categoria | Tecnologia | Versão |
|-----------|------------|---------|
| **Backend** | Django | 5.2.11 |
| **Banco de Dados** | PostgreSQL | 15 |
| **Web Server** | Gunicorn | 25.0.1 |
| **Reverse Proxy** | Nginx | latest |
| **Autenticação** | django-allauth | 65.14.0 |
| **Container** | Docker Compose | 3.8 |
| **Frontend** | Bootstrap 5 | (via CDN) |

---

## 📝 Próximos Passos / Melhorias

- [ ] Implementar exportação de relatórios (PDF/Excel)
- [ ] Dashboard com gráficos de consumo por período
- [ ] Sistema de Carrinho para retirada do estoque
- [ ] Sistema de alertas de estoque mínimo
- [ ] API REST completa para integrações
- [ ] Logs de auditoria mais detalhados
- [ ] Suporte a mais localizações
- [ ] App mobile (React Native?)

---

## 📄 Licença

Este projeto é proprietário da **ClearIT**.

---

## 📞 Suporte

Para dúvidas ou problemas, entre em contato com a equipe de Infraestrutura.

---

**Última atualização:** Março 2026  
**Versão:** 1.0.0