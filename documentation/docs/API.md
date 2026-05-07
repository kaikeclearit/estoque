# 🔌 Documentação da API

Este documento descreve todos os endpoints disponíveis no sistema.

---

## 🌐 Endpoints Disponíveis

### Autenticação

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| GET | `/login/` | Página de login | Público |
| POST | `/login/` | Autentica usuário | Público |
| GET | `/logout/` | Encerra sessão | Público |
| GET | `/accounts/microsoft/login/` | Login via Microsoft SSO | Público |

---

### Produtos

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/produtos/` | Lista todos os produtos | Login |
| GET | `/produtos/novo/` | Formulário de criação | `add_product` |
| POST | `/produtos/novo/` | Criar produto | `add_product` |
| GET | `/produtos/editar/<id>/` | Formulário de edição | `change_product` |
| POST | `/produtos/editar/<id>/` | Atualizar produto | `change_product` |
| POST | `/produtos/excluir/<id>/` | Deletar produto | `delete_product` |
| GET | `/produtos/<id>/historico-entradas/` | Modal de histórico | Login |

#### Exemplo: Listar Produtos

**Request:**
```http
GET /produtos/?search=mouse&location=MAO
Cookie: sessionid=xxx
```

**Response (HTML):**
```html
<!-- Renderiza template core/products/list.html -->
<!-- Com context: -->
{
    "products": QuerySet[Product],
    "search_query": "mouse",
    "location_filter": "MAO",
    "stats": {
        "total": 15,
        "alert": 3,
        "active": 12
    }
}
```

**Parâmetros de Query:**
- `search` (string): Busca em nome, modelo ou fabricante
- `location` (string): Filtro por local (`MAO`, `SP`, `TODOS`)

---

### Clientes

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/clientes/` | Lista todos os clientes | Login |
| GET | `/clientes/novo/` | Formulário de criação | `add_client` |
| POST | `/clientes/novo/` | Criar cliente | `add_client` |
| GET | `/clientes/editar/<id>/` | Formulário de edição | `change_client` |
| POST | `/clientes/editar/<id>/` | Atualizar cliente | `change_client` |
| GET | `/clientes/<id>/historico/` | Modal de histórico | Login |

#### Exemplo: Histórico de Cliente

**Request:**
```http
GET /clientes/42/historico/
Cookie: sessionid=xxx
```

**Response (HTML):**
```html
<!-- Renderiza template core/clients/_history_modal_content.html -->
<!-- Com context: -->
{
    "client": Client(id=42, name="CLEARIT - Manaus"),
    "history": QuerySet[
        StockOut(product="Mouse", quantity=5, created_at="2026-03-01"),
        StockOut(product="Teclado", quantity=3, created_at="2026-02-15"),
        ...
    ]
}
```

---

### Movimentações - Entradas

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/entrada/nova/` | Formulário de entrada | `add_stockentry` |
| POST | `/entrada/nova/` | Registrar entrada | `add_stockentry` |
| GET | `/entrada/historico/` | Histórico de entradas | Login |

#### Exemplo: Criar Entrada

**Request:**
```http
POST /entrada/nova/
Content-Type: application/x-www-form-urlencoded
Cookie: sessionid=xxx

product=15&entry_type=COMPRA&nf_number=12345&location=MAO&quantity=50
```

**Response (Redirect):**
```http
HTTP/1.1 302 Found
Location: /produtos/
Set-Cookie: messages=...
```

**Mensagem de Sucesso:**
```
"Entrada registrada com sucesso!"
```

**Comportamento:**
1. Valida formulário
2. Cria `StockEntry` com `employee = request.user`
3. **Transação Atômica:**
   - Trava `ProductStock` com `select_for_update()`
   - Incrementa `quantity += 50`
   - Salva
4. Redireciona para lista de produtos

---

### Movimentações - Saídas

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/saida/nova/` | Formulário de saída | `add_stockout` |
| POST | `/saida/nova/` | Registrar saída | `add_stockout` |
| GET | `/saida/historico/` | Histórico de saídas | Login |
| POST | `/saida/reverter/<id>/` | Reverter saída | `change_stockout` |

#### Exemplo: Criar Saída (Sucesso)

**Request:**
```http
POST /saida/nova/
Content-Type: application/x-www-form-urlencoded
Cookie: sessionid=xxx

product=15&location=MAO&movement_type=SAIDA&client=5&quantity=10&observation=Entrega%20emergencial
```

**Response:**
```http
HTTP/1.1 302 Found
Location: /produtos/
```

**Comportamento:**
1. Valida formulário
2. Cria `StockOut` com `employee = request.user`
3. **Validação de Estoque:**
   - Trava `ProductStock` com `select_for_update()`
   - Verifica se `quantity >= 10`
   - Se OK: `quantity -= 10`
   - Se NOK: lança `ValueError`
4. Se tipo = `RESERVA`, dispara signal → webhook

#### Exemplo: Criar Saída (Erro de Estoque)

**Request:**
```http
POST /saida/nova/
...
quantity=100
```

**Response (HTML):**
```html
<!-- Reexibe formulário com erro -->
<div class="alert alert-danger">
    Estoque insuficiente! Disponível: 40, Solicitado: 100
</div>
```

#### Exemplo: Reverter Saída

**Request:**
```http
POST /saida/reverter/123/
Cookie: sessionid=xxx
```

**Response:**
```http
HTTP/1.1 302 Found
Location: /historico/
```

**Comportamento:**
1. Busca `StockOut(id=123)`
2. Valida se não foi cancelada antes
3. **Transação Atômica:**
   - Trava `ProductStock`
   - `quantity += saída.quantity`
   - Marca `is_cancelled=True`, `cancelled_by=user`, `cancelled_at=now()`
4. Redireciona para histórico

---

### Reservas (Confirmação via Email)

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| GET | `/reserva/confirmar/<token>/` | Página de confirmação | Público |
| POST | `/reserva/confirmar/<token>/` | Confirmar reserva | Público |
| GET | `/reserva/cancelar/<token>/` | Página de cancelamento | Público |
| POST | `/reserva/cancelar/<token>/` | Cancelar reserva | Público |

#### Exemplo: Confirmar Reserva

**Request:**
```http
POST /reserva/confirmar/550e8400-e29b-41d4-a716-446655440000/
```

**Response (HTML):**
```html
<!-- Template: core/reservation_confirmed.html -->
<h1>✅ Reserva Confirmada</h1>
<p>O material foi marcado como retirado.</p>
```

**Comportamento:**
1. Busca `ReservationToken(token=uuid)`
2. Valida:
   - Token existe?
   - Já foi processado?
   - Está expirado?
3. Se OK:
   - `StockOut.movement_type = 'SAIDA'`
   - `ReservationToken.confirmed = True`
   - `ReservationToken.action = 'CONFIRMED'`

#### Exemplo: Cancelar Reserva

**Request:**
```http
POST /reserva/cancelar/550e8400-e29b-41d4-a716-446655440000/
```

**Response (HTML):**
```html
<!-- Template: core/reservation_cancelled.html -->
<h1>❌ Reserva Cancelada</h1>
<p>O estoque foi devolvido.</p>
```

**Comportamento:**
1. Valida token
2. **Devolve estoque:**
   - `ProductStock.quantity += saída.quantity`
3. Marca token como processado:
   - `confirmed = True`
   - `action = 'CANCELLED'`

#### Possíveis Erros

**Token já processado:**
```html
<!-- Template: core/reservation_already_processed.html -->
<p>Esta reserva já foi {{ action }}.</p>
```

**Token expirado:**
```html
<!-- Template: core/reservation_expired.html -->
<p>Este link expirou. Entre em contato com o setor responsável.</p>
```

---

### Histórico Unificado

| Método | Endpoint | Descrição | Permissão |
|--------|----------|-----------|-----------|
| GET | `/historico/` | Entradas + Saídas em abas | Login |

**Response Context:**
```python
{
    "entries": QuerySet[StockEntry].order_by('-created_at'),
    "outputs": QuerySet[StockOut].order_by('-created_at')
}
```

---

### API JSON

| Método | Endpoint | Descrição | Autenticação |
|--------|----------|-----------|--------------|
| GET | `/api/product-stock/` | Consulta estoque JSON | Login |

#### Exemplo: Consultar Estoque

**Request:**
```http
GET /api/product-stock/?product=15&location=MAO
Cookie: sessionid=xxx
```

**Response (JSON):**
```json
{
  "quantity": 45,
  "product": "Mouse Logitech MX Master 3",
  "location": "Manaus"
}
```

**Parâmetros:**
- `product` (int, obrigatório): ID do produto
- `location` (string, opcional): Filtro por local

**Erro - Produto não informado:**
```json
{
  "error": "Product ID required"
}
```

**Produto sem estoque:**
```json
{
  "quantity": 0,
  "message": "Produto sem estoque"
}
```

---

## 🔐 Autenticação e Permissões

### Sistema de Sessão
O sistema usa sessões do Django (`django.contrib.sessions`).

**Cookie de Sessão:**
```
sessionid=a1b2c3d4e5f6g7h8i9j0
```

### Grupos de Permissões

#### Gestores
Permissões:
- `core.add_product`
- `core.change_product`
- `core.delete_product`
- `core.add_client`
- `core.change_client`
- `core.add_stockentry`
- `core.add_stockout`
- `core.change_stockout`

#### Usuários Padrão
Somente leitura (visualização).

### Validação de Permissões

**Decorator nas views:**
```python
@permission_required('core.add_stockentry', raise_exception=True)
def entry_create(request):
    # ...
```

**URLs protegidas:**
```python
path('produtos/novo/', 
     gestor_only('add_product')(products.product_create), 
     name='product_create')
```

**Resposta quando não autorizado:**
```http
HTTP/1.1 403 Forbidden
Content-Type: text/html

<!-- Template: 403.html -->
<h1>🚫 Acesso Negado</h1>
<p>Você não tem permissão para acessar esta página.</p>
```

---

## 🌐 Integração com Serviços Externos

### Webhook - Make.com (Envio de Emails)

**Endpoint:** Configurado em `settings.RESERVATION_WEBHOOK_URL`

**Trigger:** Signal `post_save` em `StockOut` quando `movement_type=RESERVA`

**Payload Enviado:**
```json
{
  "to_email": "usuario@clearit.com",
  "to_name": "João Silva",
  "product_name": "Mouse Logitech",
  "client_name": "CLEARIT - Manaus",
  "quantity": 5,
  "location": "Manaus",
  "reservation_date": "01/03/2026",
  "scheduled_date": "15/03/2026",
  "confirm_url": "https://estoque.clearit.com/reserva/confirmar/550e8400-...",
  "cancel_url": "https://estoque.clearit.com/reserva/cancelar/550e8400-...",
  "expires_days": 7,
  "reservation_id": 123
}
```

**Código:**
```python
# core/services/webhook_service.py
import requests

def send_reservation_webhook(stock_out, token):
    payload = {
        # ... (ver acima)
    }
    
    try:
        response = requests.post(
            settings.RESERVATION_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Erro webhook: {e}")
        return False
```

### Microsoft Azure AD (SSO)

**Provider:** `django-allauth` com `microsoft`

**Callback URL:** `/accounts/microsoft/login/callback/`

**Dados Retornados:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "displayName": "João Silva",
  "mail": "joao.silva@clearit.com",
  "jobTitle": "Analista de Infraestrutura",
  "department": "TI"
}
```

**Signal de Login:**
```python
@receiver(user_logged_in)
def atualizar_permissoes_microsoft(request, user, **kwargs):
    social_account = user.socialaccount_set.filter(provider='microsoft').first()
    job_title = social_account.extra_data.get('jobTitle', '').lower()
    
    # Verifica se é gestor e atualiza grupos
```

---

## 📊 Formatos de Resposta

### HTML (Padrão)
Todas as views retornam templates HTML renderizados.

### JSON (API)
Apenas o endpoint `/api/product-stock/` retorna JSON.

**Headers:**
```
Content-Type: application/json
```

---

## ⚠️ Tratamento de Erros

### Erro 400 - Bad Request
```json
{
  "error": "Product ID required"
}
```

### Erro 403 - Forbidden
```html
<!-- Template 403.html -->
<h1>Acesso Negado</h1>
```

### Erro 404 - Not Found
```html
<!-- Template 404.html -->
<h1>Página Não Encontrada</h1>
```

### Erro 500 - Internal Server Error
```html
<!-- Template 500.html -->
<h1>Erro Interno</h1>
```

**Log de Erros:**
```python
# Em caso de erro em movimentação
except ValueError as e:
    messages.error(request, str(e))  # "Estoque insuficiente!"
except Exception as e:
    messages.error(request, f"Erro inesperado: {str(e)}")
```

---

## 🧪 Exemplos de Uso com cURL

### Login
```bash
curl -X POST http://localhost/login/ \
  -d "username=joao&password=senha123" \
  -c cookies.txt
```

### Criar Entrada
```bash
curl -X POST http://localhost/entrada/nova/ \
  -b cookies.txt \
  -d "product=15&entry_type=COMPRA&nf_number=12345&location=MAO&quantity=50"
```

### Consultar Estoque (API)
```bash
curl http://localhost/api/product-stock/?product=15 \
  -b cookies.txt
```

---

## 📋 Notas Importantes

1. **CSRF Protection:** Todas as requisições POST precisam incluir o token CSRF
2. **Rate Limiting:** Não implementado (adicionar em produção se necessário)
3. **Versionamento:** Não há versionamento de API (v1, v2, etc.)
4. **Documentação Interativa:** Considerar implementar Swagger/OpenAPI no futuro

---

**Última atualização:** Março 2026