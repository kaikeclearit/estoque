# 🏛️ Decisões Técnicas e Arquitetura

Documentação das principais decisões técnicas tomadas no projeto e suas justificativas.

---

## 🎯 Filosofia do Projeto

### Princípios

1. **Simplicidade > Complexidade:** Soluções diretas quando possível
2. **Segurança em Primeiro Lugar:** Proteção contra race conditions e dados inconsistentes
3. **Auditoria Completa:** Todo histórico é preservado
4. **Imutabilidade de Registros:** Movimentações não são editadas, apenas revertidas
5. **Transações Atômicas:** Tudo acontece ou nada acontece

---

## 🗄️ Decisões de Arquitetura

### 1. Por que Django?

**Decisão:** Usar Django como framework backend

**Justificativa:**
- ✅ **ORM Robusto:** Abstração do banco com migrations automáticas
- ✅ **Admin Built-in:** Interface administrativa pronta
- ✅ **django-allauth:** Integração SSO Microsoft facilitada
- ✅ **Comunidade Ativa:** Grande ecossistema de bibliotecas
- ✅ **Segurança:** Proteção CSRF, SQL Injection, XSS por padrão

**Alternativas Consideradas:**
- Flask: Muito minimalista, exigiria mais código boilerplate
- FastAPI: Foco em APIs, não tem admin/templates nativos

---

### 2. Por que PostgreSQL?

**Decisão:** Usar PostgreSQL como banco de dados

**Justificativa:**
- ✅ **ACID Compliant:** Transações atômicas garantidas
- ✅ **SELECT FOR UPDATE:** Trava de registros para prevenir race conditions
- ✅ **Constraints Avançadas:** CHECK constraints no nível do banco
- ✅ **JSON Support:** Caso precise armazenar dados semi-estruturados
- ✅ **Performance:** Excelente para reads e writes concorrentes

**Alternativas Consideradas:**
- SQLite: Não suporta concorrência adequadamente
- MySQL: Menos features avançadas que PostgreSQL

---

### 3. Arquitetura de Estoque: Tabela Pivô

**Decisão:** Criar tabela `ProductStock` separada para quantidade

**Estrutura:**
```
Product (dados imutáveis)
    ↓
ProductStock (produto + localização + quantidade)
    ↓
StockEntry/StockOut (auditoria de movimentações)
```

**Justificativa:**
- ✅ **Normalização:** Produto não muda quando estoque muda
- ✅ **Multi-localidade:** Fácil adicionar novos locais
- ✅ **Consultas Rápidas:** `ProductStock.quantity` é sempre o valor atual
- ✅ **Auditoria:** Histórico completo em tabelas separadas

**Alternativa Descartada:**
```python
# ❌ RUIM: Quantidade no modelo Product
class Product:
    quantity_mao = models.IntegerField()
    quantity_sp = models.IntegerField()
```

**Problemas:**
- Não escala para novos locais
- Dificulta auditoria
- Queries complexas para totais

---

### 4. Proteção Contra Race Conditions

**Problema:** Dois usuários baixam estoque ao mesmo tempo

**Cenário:**
```
Estoque atual: 10 unidades

Thread A lê: 10 unidades       Thread B lê: 10 unidades
Thread A salva: 10 - 5 = 5     Thread B salva: 10 - 7 = 3
                                ❌ ERRO! Deveria ser -2 (estoque negativo)
```

**Solução Implementada:**

```python
with transaction.atomic():
    # 🔒 Trava o registro até a transação terminar
    stock = ProductStock.objects.select_for_update().get(
        product=produto,
        location=local
    )
    
    # Validação
    if stock.quantity < quantidade:
        raise ValueError("Estoque insuficiente")
    
    # Atualização
    stock.quantity -= quantidade
    stock.save()
    # 🔓 Liberado aqui
```

**Como Funciona:**
1. `select_for_update()` faz `SELECT ... FOR UPDATE` no SQL
2. Thread A trava o registro
3. Thread B aguarda Thread A terminar
4. Thread B lê o valor NOVO (5) e valida corretamente

**Alternativas Consideradas:**
- **Validação no Form:** ❌ Não protege contra concorrência
- **Locking no Application Level:** ❌ Não funciona em múltiplos processos
- **Optimistic Locking:** Possível, mas mais complexo

---

### 5. Imutabilidade de Movimentações

**Decisão:** StockEntry e StockOut não podem ser editadas

**Justificativa:**
- ✅ **Auditoria:** Histórico preservado
- ✅ **Rastreabilidade:** Saber exatamente o que aconteceu e quando
- ✅ **Segurança:** Evita adulteração de dados

**Como Corrigir Erros:**
- Entrada errada → Criar entrada negativa (AJUSTE)
- Saída errada → Reverter saída (cria registro de cancelamento)

**Implementação:**
```python
class StockOut(models.Model):
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True)
    cancelled_by = models.ForeignKey(Employee, ...)
```

---

### 6. Sistema de Reservas via Email

**Decisão:** Usar webhook externo (Make.com) para envio de emails

**Fluxo:**
```
Django → Signal → Webhook → Make.com → Gmail
```

**Justificativa:**
- ✅ **Desacoplamento:** Django não precisa configurar SMTP
- ✅ **Flexibilidade:** Fácil mudar provedor de email
- ✅ **Templates Visuais:** Make.com tem editor visual
- ✅ **Rastreamento:** Make.com registra disparos

**Alternativa Considerada:**
- **Django Email Backend:** Funcional, mas:
  - ❌ Configuração de SMTP complexa
  - ❌ Templates em HTML puro no código
  - ❌ Sem retry automático

**Token System:**
```python
ReservationToken
    token = UUIDField()  # ← Único, não adivinhável
    expires_at = DateTimeField()  # ← Expira em 7 dias
```

**Segurança:**
- UUID4 tem 2^122 possibilidades (~5.3 × 10^36)
- Impossível adivinhar por força bruta
- Expira automaticamente

---

### 7. Autenticação Híbrida

**Decisão:** Suportar Login Local + Microsoft SSO

**Justificativa:**
- ✅ **Contingência:** Se Azure AD cair, login local funciona
- ✅ **Contas de Serviço:** Usuários técnicos sem email Microsoft
- ✅ **Migração Gradual:** Pode migrar aos poucos

**Implementação:**
```python
class Employee(AbstractUser):
    microsoft_oid = models.CharField(unique=True, null=True)
    login_type = models.CharField(choices=[
        ('LOCAL', 'Senha Local'),
        ('MS', 'Microsoft SSO'),
        ('HYBRID', 'Híbrido'),
    ])
```

**Signal de Sincronização:**
```python
@receiver(user_logged_in)
def atualizar_permissoes_microsoft(request, user, **kwargs):
    # Atualiza grupos baseado em jobTitle do Azure AD
```

---

### 8. Sistema de Permissões

**Decisão:** Usar Groups do Django + Permissões Padrão

**Estrutura:**
```
Group: Gestores
    ├─ core.add_product
    ├─ core.change_product
    ├─ core.delete_product
    ├─ core.add_stockentry
    ├─ core.add_stockout
    └─ core.change_stockout (reverter)

Usuários Padrão: Sem grupo = Somente leitura
```

**Justificativa:**
- ✅ **Nativo do Django:** Não precisa biblioteca externa
- ✅ **Granular:** Controla por model
- ✅ **Auditável:** Django Admin mostra quem tem o quê

**Alternativa Considerada:**
- **django-guardian (Object-level permissions):** Muito complexo para a necessidade

---

### 9. Docker Multi-Stage Build

**Decisão:** Usar containers separados para Nginx, Django e PostgreSQL

**Arquitetura:**
```
nginx:80 → gunicorn:8000 → postgres:5432
```

**Justificativa:**
- ✅ **Isolamento:** Cada serviço em seu container
- ✅ **Escalabilidade:** Fácil replicar containers Django
- ✅ **Manutenção:** Atualiza um serviço sem afetar outros
- ✅ **Performance:** Nginx serve estáticos, Gunicorn foca em lógica

**Volumes Compartilhados:**
```yaml
volumes:
  static_volume:  # ← Nginx e Django compartilham
  media_volume:   # ← Nginx e Django compartilham
  postgres_data:  # ← Só PostgreSQL
```

---

## 🔧 Decisões de Implementação

### 1. Formulário Único para Entrada/Saída

**Decisão:** Template `stock/form.html` reutilizado

**Implementação:**
```python
# views/movements.py
def entry_create(request):
    return render(request, 'core/stock/form.html', {
        'form': StockEntryForm(),
        'title': 'Registrar Entrada',
        'btn_class': 'btn-success',
        'icon': 'bi-box-arrow-in-down'
    })

def output_create(request):
    return render(request, 'core/stock/form.html', {
        'form': StockOutForm(),
        'title': 'Registrar Saída',
        'btn_class': 'btn-danger',
        'icon': 'bi-box-arrow-up'
    })
```

**Justificativa:**
- ✅ **DRY:** Não duplica HTML
- ✅ **Consistência:** UX uniforme
- ✅ **Manutenção:** Corrige bug em um lugar só

---

### 2. Messages Framework

**Decisão:** Usar `django.contrib.messages` para feedback

**Exemplo:**
```python
messages.success(request, 'Entrada registrada com sucesso!')
messages.error(request, f'Estoque insuficiente! Disponível: {qty}')
```

**Justificativa:**
- ✅ **UX:** Feedback imediato ao usuário
- ✅ **Nativo:** Integrado ao Django
- ✅ **Flash Messages:** Desaparecem após exibição

---

### 3. HTMX para Modais (Não Implementado Ainda)

**Recomendação Futura:** Usar HTMX para carregar modais dinamicamente

**Benefício:**
- Histórico de entradas sem recarregar página
- Melhor UX

**Exemplo:**
```html
<button hx-get="/produtos/123/historico-entradas/" 
        hx-target="#modal-content">
    Ver Histórico
</button>
```

---

## 📊 Trade-offs

### 1. Webhook vs Email Nativo

**Escolhido:** Webhook (Make.com)  
**Vantagem:** Flexibilidade, templates visuais  
**Desvantagem:** Dependência externa, latência adicional  
**Mitigação:** Falha no webhook não impede reserva (erro é logado)

---

### 2. Transações vs Performance

**Escolhido:** Transações atômicas com locks  
**Vantagem:** Dados consistentes, zero bugs de concorrência  
**Desvantagem:** Pequena redução de throughput  
**Justificativa:** Integridade > Performance (estoques não têm milhões de ops/s)

---

### 3. Auditoria Completa vs Storage

**Escolhido:** Manter todo histórico  
**Vantagem:** Rastreabilidade total  
**Desvantagem:** Banco cresce ilimitadamente  
**Mitigação:** Arquivar registros antigos (tarefa futura)

---

## 🚀 Melhorias Futuras

### 1. Cache com Redis

**Problema:** Queries repetitivas em listagens

**Solução:**
```python
from django.core.cache import cache

def product_list(request):
    products = cache.get('products_list')
    if not products:
        products = Product.objects.prefetch_related('stocks')
        cache.set('products_list', products, 300)  # 5 min
    # ...
```

### 2. Celery para Tasks Assíncronas

**Use Cases:**
- Enviar emails sem bloquear request
- Gerar relatórios pesados
- Processar importações em lote

**Exemplo:**
```python
@shared_task
def send_reservation_email(stock_out_id, token_id):
    # Executa em background worker
    pass
```

### 3. API REST com Django REST Framework

**Benefício:**
- Apps mobile podem consumir
- Integrações com outros sistemas
- Documentação automática (Swagger)

### 4. Elasticsearch para Buscas

**Benefício:**
- Busca full-text mais rápida
- Autocomplete em tempo real
- Filtros complexos

---

## 📚 Referências

### Artigos e Discussões

- [Django select_for_update](https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-for-update)
- [ACID Transactions in PostgreSQL](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [OAuth 2.0 Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)

### Livros

- Two Scoops of Django (Audrey Roy Greenfeld)
- High Performance Django (Peter Baumgartner)

---

## 🤔 Perguntas Frequentes

### Por que não usar SQLAlchemy?

Django ORM é suficiente para o escopo do projeto e tem melhor integração com o ecossistema Django.

### Por que Gunicorn e não uWSGI?

Gunicorn é mais simples de configurar e suficiente para a carga esperada.

### Por que Bootstrap e não Tailwind?

Bootstrap tem componentes prontos (modais, cards) que aceleram o desenvolvimento. Tailwind seria melhor para designs totalmente customizados.

### Por que não usar DRF desde o início?

CRUD simples não precisa de API. DRF adiciona complexidade desnecessária se não há consumo externo.

---

**Última atualização:** Março 2026  
**Versão:** 1.0.0