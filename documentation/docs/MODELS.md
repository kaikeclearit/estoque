# 📊 Documentação dos Modelos de Dados

Esta documentação detalha cada modelo do sistema, seus campos, relacionamentos e regras de negócio.

---

## 1. Employee (Usuário do Sistema)

**Herda de:** `AbstractUser` (Django)

### Descrição
Modelo de usuário customizado que suporta autenticação híbrida: senha local tradicional + Microsoft Single Sign-On (SSO).

### Campos

| Campo | Tipo | Descrição | Obrigatório | Único |
|-------|------|-----------|-------------|-------|
| `id` | AutoField | Identificador único | ✅ | ✅ |
| `username` | CharField(150) | Nome de usuário para login | ✅ | ✅ |
| `email` | EmailField | Email do usuário | ✅ | ❌ |
| `password` | CharField(128) | Hash da senha (bcrypt) | ✅ | ❌ |
| `microsoft_oid` | CharField(255) | Object ID do Azure AD | ❌ | ✅ |
| `login_type` | CharField(10) | Tipo de autenticação | ✅ | ❌ |
| `department` | CharField(100) | Departamento/Setor | ❌ | ❌ |
| `first_name` | CharField(150) | Primeiro nome | ❌ | ❌ |
| `last_name` | CharField(150) | Sobrenome | ❌ | ❌ |
| `is_active` | BooleanField | Usuário ativo? | ✅ | ❌ |
| `is_staff` | BooleanField | Acesso ao admin? | ✅ | ❌ |
| `is_superuser` | BooleanField | Superusuário? | ✅ | ❌ |
| `date_joined` | DateTimeField | Data de cadastro | ✅ | ❌ |

### Choices: `login_type`
- `LOCAL`: Autenticação por senha local
- `MS`: Autenticação exclusiva via Microsoft
- `HYBRID`: Suporta ambos os métodos

### Relacionamentos
- **1:N com StockEntry** (campo `employee`) - Entradas registradas
- **1:N com StockOut** (campo `employee`) - Saídas registradas
- **1:N com StockOut** (campo `cancelled_by`) - Saídas canceladas

### Regras de Negócio
1. **Sincronização Automática de Grupos:**
   - Ao fazer login via Microsoft, o sistema verifica o campo `jobTitle` no Azure AD
   - Se o cargo contém: "infraestrutura", "pós-vendas", "projetos", "suporte" ou "qualidade" → Adiciona ao grupo **Gestores**
   - Caso contrário → Remove do grupo Gestores (se estava)

2. **Permissões:**
   - **Gestores:** CRUD completo
   - **Demais usuários:** Somente leitura

### Signal Relacionado
```python
@receiver(user_logged_in)
def atualizar_permissoes_microsoft(request, user, **kwargs):
    # Atualiza grupos baseado no jobTitle do Azure AD
```

---

## 2. Product (Produto)

### Descrição
Cadastro imutável do produto. **NÃO contém quantidade**, pois a quantidade é armazenada por localização em `ProductStock`.

### Campos

| Campo | Tipo | Descrição | Obrigatório | Único |
|-------|------|-----------|-------------|-------|
| `id` | AutoField | Identificador único | ✅ | ✅ |
| `name` | CharField(255) | Nome do produto | ✅ | ❌ |
| `model` | CharField(255) | Modelo | ❌ | ❌ |
| `manufacturer` | CharField(255) | Fabricante | ❌ | ❌ |
| `product_id` | CharField(255) | ID/SKU do produto | ❌ | ✅ |

### Relacionamentos
- **1:N com ProductStock** - Um produto pode ter estoque em vários locais
- **1:N com StockEntry** - Histórico de entradas
- **1:N com StockOut** - Histórico de saídas

### Exemplo de Registro
```python
Product(
    name="Mouse Logitech MX Master 3",
    model="MX Master 3",
    manufacturer="Logitech",
    product_id="LOG-MX3-001"
)
```

---

## 3. ProductStock (Estoque por Localização)

### Descrição
Tabela pivô que relaciona Produto + Localização. **Esta é a fonte da verdade para quantidade disponível.**

### Campos

| Campo | Tipo | Descrição | Obrigatório | Único |
|-------|------|-----------|-------------|-------|
| `id` | AutoField | Identificador único | ✅ | ✅ |
| `product_id` | ForeignKey | Produto | ✅ | ❌ |
| `location` | CharField(3) | Localização | ✅ | ❌ |
| `quantity` | IntegerField | Quantidade disponível | ✅ | ❌ |

### Choices: `location`
- `MAO`: Manaus
- `SP`: São Paulo

### Constraints
```sql
-- Não permite estoque negativo
CHECK (quantity >= 0)

-- Único por produto + localização
UNIQUE (product_id, location)
```

### Regras de Negócio
1. **Criação automática:** Ao registrar primeira entrada/saída, cria registro com `quantity=0`
2. **Atualização automática:**
   - Entrada: `quantity += entrada.quantity`
   - Saída: `quantity -= saída.quantity` (com validação)
3. **Proteção contra Race Condition:**
   - Sempre usar `select_for_update()` antes de modificar
   - Envolver em `transaction.atomic()`

### Exemplo de Uso Seguro
```python
with transaction.atomic():
    stock = ProductStock.objects.select_for_update().get(
        product=produto,
        location='MAO'
    )
    stock.quantity += 10
    stock.save()
```

---

## 4. StockEntry (Entrada de Material)

### Descrição
Registra todas as entradas de material no estoque. **Imutável após criação** (audit log).

### Campos

| Campo | Tipo | Descrição | Obrigatório | Único |
|-------|------|-----------|-------------|-------|
| `id` | AutoField | Identificador único | ✅ | ✅ |
| `product_id` | ForeignKey | Produto | ✅ | ❌ |
| `employee_id` | ForeignKey | Responsável | ✅ | ❌ |
| `entry_type` | CharField(20) | Tipo de entrada | ✅ | ❌ |
| `nf_number` | CharField(50) | Número da NF | ❌ | ❌ |
| `location` | CharField(3) | Localização | ✅ | ❌ |
| `quantity` | PositiveIntegerField | Quantidade | ✅ | ❌ |
| `created_at` | DateTimeField | Data/hora registro | ✅ | ❌ |

### Choices: `entry_type`
- `COMPRA`: Compra de fornecedor
- `RETORNO`: Retorno de empréstimo
- `AJUSTE`: Ajuste de inventário
- `DOACAO`: Doação/Brinde recebido

### Comportamento no `save()`
```python
def save(self, *args, **kwargs):
    with transaction.atomic():
        super().save(*args, **kwargs)
        
        stock, created = ProductStock.objects.select_for_update().get_or_create(
            product=self.product, 
            location=self.location,
            defaults={'quantity': 0}
        )
        stock.quantity += self.quantity
        stock.save()
```

**Atenção:** Não permite edição. Para corrigir, reverter e criar novo registro.

---

## 5. StockOut (Saída de Material)

### Descrição
Registra todas as saídas de material. Suporta diferentes tipos de movimentação e cancelamento.

### Campos

| Campo | Tipo | Descrição | Obrigatório | Único |
|-------|------|-----------|-------------|-------|
| `id` | AutoField | Identificador único | ✅ | ✅ |
| `product_id` | ForeignKey | Produto | ✅ | ❌ |
| `client_id` | ForeignKey | Destinatário | ✅ | ❌ |
| `employee_id` | ForeignKey | Responsável | ✅ | ❌ |
| `location` | CharField(3) | Localização | ✅ | ❌ |
| `movement_type` | CharField(20) | Tipo de movimentação | ✅ | ❌ |
| `quantity` | PositiveIntegerField | Quantidade | ✅ | ❌ |
| `scheduled_date` | DateField | Data prevista | ❌ | ❌ |
| `observation` | TextField | Observações | ❌ | ❌ |
| `is_cancelled` | BooleanField | Foi cancelada? | ✅ | ❌ |
| `cancelled_at` | DateTimeField | Quando foi cancelada | ❌ | ❌ |
| `cancelled_by_id` | ForeignKey | Quem cancelou | ❌ | ❌ |
| `created_at` | DateTimeField | Data/hora registro | ✅ | ❌ |

### Choices: `movement_type`
- `SAIDA`: Saída padrão (definitiva)
- `RESERVA`: Reserva técnica (precisa confirmação)
- `EMPRESTIMO`: Empréstimo temporário
- `DESCARTE`: Descarte/Quebra

### Comportamento no `save()`
```python
def save(self, *args, **kwargs):
    with transaction.atomic():
        if not self.pk:  # Só na criação
            stock = ProductStock.objects.select_for_update().filter(
                product=self.product, 
                location=self.location
            ).first()
            
            if not stock or stock.quantity < self.quantity:
                raise ValueError(f"Estoque insuficiente! Disponível: {stock.quantity}")
            
            stock.quantity -= self.quantity
            stock.save()
        
        super().save(*args, **kwargs)
```

### Validações
1. **Estoque disponível:** Valida antes de salvar
2. **Reserva exige data:** Se `movement_type=RESERVA`, `scheduled_date` é obrigatório
3. **Cancelamento:** Só pode ser feito via método específico (não editando diretamente)

---

## 6. Client (Cliente/Setor)

### Descrição
Cadastro de clientes ou setores que recebem materiais.

### Campos

| Campo | Tipo | Descrição | Obrigatório | Único |
|-------|------|-----------|-------------|-------|
| `id` | AutoField | Identificador único | ✅ | ✅ |
| `name` | CharField(255) | Nome do cliente/setor | ✅ | ✅ |

### Relacionamentos
- **1:N com StockOut** - Histórico de saídas recebidas

### Exemplo de Registro
```python
Client(name="CLEARIT - Manaus")
Client(name="Setor de TI")
```

---

## 7. ReservationToken (Token de Confirmação)

### Descrição
Token único UUID para confirmação/cancelamento de reservas via email.

### Campos

| Campo | Tipo | Descrição | Obrigatório | Único |
|-------|------|-----------|-------------|-------|
| `id` | AutoField | Identificador único | ✅ | ✅ |
| `stock_out_id` | OneToOneField | Saída relacionada | ✅ | ✅ |
| `token` | UUIDField | Token UUID | ✅ | ✅ |
| `created_at` | DateTimeField | Data de criação | ✅ | ❌ |
| `expires_at` | DateTimeField | Data de expiração | ✅ | ❌ |
| `confirmed` | BooleanField | Foi processado? | ✅ | ❌ |
| `confirmed_at` | DateTimeField | Quando processado | ❌ | ❌ |
| `action` | CharField(20) | Ação realizada | ❌ | ❌ |

### Choices: `action`
- `CONFIRMED`: Retirada confirmada
- `CANCELLED`: Reserva cancelada

### Comportamento no `save()`
```python
def save(self, *args, **kwargs):
    if not self.expires_at:
        self.expires_at = timezone.now() + timedelta(days=7)
    super().save(*args, **kwargs)
```

### Método: `is_expired()`
```python
def is_expired(self):
    return timezone.now() > self.expires_at
```

### Ciclo de Vida
1. **Criação:** Automática via signal quando `StockOut.movement_type=RESERVA`
2. **Envio:** Webhook dispara email com URLs contendo o token
3. **Confirmação:** Usuário clica em "Confirmar" → `action=CONFIRMED`
4. **Cancelamento:** Usuário clica em "Cancelar" → Devolve estoque, `action=CANCELLED`
5. **Expiração:** Após 7 dias, token fica inválido

---

## 📐 Diagrama de Relacionamentos

```
Employee (1) ----< (N) StockEntry
Employee (1) ----< (N) StockOut [registra]
Employee (1) ----< (N) StockOut [cancela]

Product (1) ----< (N) ProductStock
Product (1) ----< (N) StockEntry
Product (1) ----< (N) StockOut

Client (1) ----< (N) StockOut

StockOut (1) ---- (1) ReservationToken
```

---

## 🔒 Constraints e Índices Importantes

### Constraints de Banco
```sql
-- ProductStock: Não permite estoque negativo
ALTER TABLE core_productstock 
ADD CONSTRAINT quantity_non_negative 
CHECK (quantity >= 0);

-- ProductStock: Único por produto + localização
ALTER TABLE core_productstock 
ADD CONSTRAINT unique_product_location 
UNIQUE (product_id, location);
```

### Índices Recomendados
```sql
-- Busca rápida por localização
CREATE INDEX idx_productstock_location ON core_productstock(location);

-- Histórico por data
CREATE INDEX idx_stockentry_created ON core_stockentry(created_at DESC);
CREATE INDEX idx_stockout_created ON core_stockout(created_at DESC);

-- Filtros comuns
CREATE INDEX idx_stockout_type ON core_stockout(movement_type);
CREATE INDEX idx_stockout_cancelled ON core_stockout(is_cancelled);
```

---

## 🎯 Boas Práticas

### 1. Sempre usar transações para alterações de estoque
```python
from django.db import transaction

with transaction.atomic():
    stock = ProductStock.objects.select_for_update().get(pk=1)
    stock.quantity += 10
    stock.save()
```

### 2. Nunca editar StockEntry ou StockOut
São registros de auditoria. Para corrigir:
- **Entrada:** Criar ajuste negativo
- **Saída:** Usar função de reversão

### 3. Validar permissões nas views
```python
@permission_required('core.add_stockentry', raise_exception=True)
def entry_create(request):
    # ...
```

### 4. Usar select_related nas listagens
```python
# Evita N+1 queries
entries = StockEntry.objects.select_related(
    'product', 'employee'
).order_by('-created_at')
```

---

**Última atualização:** Março 2026