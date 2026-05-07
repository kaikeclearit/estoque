# 📖 Casos de Uso

Este documento descreve os principais casos de uso do sistema, organizados por perfil de usuário.

---

## 👥 Perfis de Usuário

### Gestor
Usuários do grupo "Gestores" identificados pelo cargo no Azure AD.

**Permissões:**
- ✅ CRUD completo de produtos
- ✅ CRUD completo de clientes
- ✅ Registrar entradas e saídas
- ✅ Reverter movimentações
- ✅ Visualizar históricos

**Setores com perfil Gestor:**
- Infraestrutura
- Pós-Vendas
- Projetos
- Suporte
- Qualidade

### Usuário Padrão
Demais colaboradores da empresa.

**Permissões:**
- ✅ Visualizar produtos e estoques
- ✅ Visualizar clientes
- ✅ Consultar históricos
- ❌ Criar/editar/excluir registros

---

## 📦 UC-01: Cadastrar Novo Produto

**Ator:** Gestor  
**Pré-condição:** Usuário autenticado e com permissão `add_product`

### Fluxo Principal

1. Gestor acessa menu "Produtos"
2. Clica em "➕ Novo Produto"
3. Preenche formulário:
   - Nome do produto (obrigatório)
   - Modelo (opcional)
   - Fabricante (opcional)
   - ID do Produto (opcional, único)
4. Clica em "Salvar"
5. Sistema valida dados
6. Sistema cria registro `Product`
7. Sistema redireciona para lista de produtos
8. Exibe mensagem de sucesso

### Fluxo Alternativo 3a - Dados Inválidos

3a.1. Sistema exibe erros de validação  
3a.2. Retorna ao passo 3

### Fluxo Alternativo 3b - ID Duplicado

3b.1. Sistema exibe erro "Este ID já existe"  
3b.2. Retorna ao passo 3

### Regras de Negócio

- **RN-01:** Nome é obrigatório
- **RN-02:** ID do Produto, se informado, deve ser único
- **RN-03:** Produto criado não possui estoque inicial (zerado em todos os locais)

---

## 📥 UC-02: Registrar Entrada de Material

**Ator:** Gestor  
**Pré-condição:** Usuário autenticado e com permissão `add_stockentry`

### Fluxo Principal

1. Gestor acessa "Movimentações" → "Nova Entrada"
2. Preenche formulário:
   - Produto (seleção)
   - Tipo de Entrada (COMPRA, RETORNO, AJUSTE, DOACAO)
   - Número da NF (opcional)
   - Localização (MAO ou SP)
   - Quantidade (número positivo)
3. Clica em "Salvar"
4. Sistema inicia transação atômica
5. Sistema cria registro `StockEntry` com `employee = usuário logado`
6. Sistema busca ou cria `ProductStock` para produto+localização
7. Sistema trava registro com `select_for_update()`
8. Sistema incrementa `quantity += entrada.quantity`
9. Sistema commita transação
10. Sistema redireciona para lista de produtos
11. Exibe mensagem "Entrada registrada com sucesso!"

### Fluxo Alternativo 3a - Dados Inválidos

3a.1. Sistema exibe erros de validação  
3a.2. Retorna ao passo 2

### Fluxo Alternativo 5a - Erro na Transação

5a.1. Sistema faz rollback automático  
5a.2. Exibe mensagem de erro  
5a.3. Retorna ao passo 2

### Regras de Negócio

- **RN-04:** Quantidade deve ser positiva
- **RN-05:** Entrada é imutável (não pode ser editada após criação)
- **RN-06:** Entradas sempre incrementam o estoque
- **RN-07:** Responsável é preenchido automaticamente com usuário logado

### Exemplo Prático

**Cenário:** Receber compra de 50 mouses em Manaus

1. Produto: "Mouse Logitech MX Master 3"
2. Tipo: COMPRA
3. NF: 12345
4. Local: MAO
5. Quantidade: 50

**Resultado:**
- Cria `StockEntry(quantity=50)`
- Atualiza `ProductStock(product=Mouse, location=MAO, quantity=50)`

---

## 📤 UC-03: Registrar Saída de Material

**Ator:** Gestor  
**Pré-condição:** Usuário autenticado e com permissão `add_stockout`

### Fluxo Principal

1. Gestor acessa "Movimentações" → "Nova Saída"
2. Preenche formulário:
   - Produto
   - Localização
   - Tipo de Movimentação (SAIDA, RESERVA, EMPRESTIMO, DESCARTE)
   - Cliente/Setor destinatário
   - Quantidade
   - Data Prevista (se tipo = RESERVA)
   - Observação (opcional)
3. Clica em "Salvar"
4. Sistema inicia transação atômica
5. Sistema busca `ProductStock` e trava com `select_for_update()`
6. Sistema valida: `stock.quantity >= saída.quantity`?
7. Se válido:
   - Decrementa `quantity -= saída.quantity`
   - Cria `StockOut` com `employee = usuário logado`
   - Commita transação
8. Se tipo = RESERVA:
   - Signal dispara criação de `ReservationToken`
   - Webhook envia email para `employee.email`
9. Redireciona para lista de produtos
10. Exibe mensagem de sucesso

### Fluxo Alternativo 6a - Estoque Insuficiente

6a.1. Sistema exibe erro "Estoque insuficiente! Disponível: X, Solicitado: Y"  
6a.2. Faz rollback da transação  
6a.3. Reexibe formulário com dados preenchidos  
6a.4. Retorna ao passo 2

### Fluxo Alternativo 2a - Tipo RESERVA sem Data

2a.1. Sistema valida formulário  
2a.2. Exibe erro "Para reservas, é obrigatório informar a data prevista"  
2a.3. Retorna ao passo 2

### Regras de Negócio

- **RN-08:** Só permite saída se houver estoque disponível
- **RN-09:** Validação de estoque usa `select_for_update()` para evitar race condition
- **RN-10:** Saída tipo RESERVA exige data prevista
- **RN-11:** Saída é imutável (só pode ser revertida, não editada)
- **RN-12:** Responsável é preenchido automaticamente

### Exemplo Prático

**Cenário:** Emprestar 5 mouses para cliente "CLEARIT - Manaus"

**Input:**
- Produto: Mouse Logitech
- Local: MAO
- Tipo: EMPRESTIMO
- Cliente: CLEARIT - Manaus
- Quantidade: 5
- Obs: "Evento de treinamento"

**Estoque Antes:** 50 unidades  
**Estoque Depois:** 45 unidades

---

## 🔔 UC-04: Criar Reserva Técnica

**Ator:** Gestor  
**Pré-condição:** Usuário autenticado e com permissão `add_stockout`

### Fluxo Principal

1. Gestor acessa "Movimentações" → "Nova Saída"
2. Preenche formulário:
   - Produto
   - Local
   - Tipo: **RESERVA**
   - Cliente
   - Quantidade
   - Data Prevista: 15/03/2026
   - Observação: "Instalação no cliente X"
3. Clica em "Salvar"
4. Sistema valida estoque (igual UC-03)
5. Sistema cria `StockOut` com `movement_type=RESERVA`
6. Signal `post_save` dispara automaticamente
7. Sistema cria `ReservationToken`:
   - `token = UUID único`
   - `expires_at = now() + 7 dias`
8. Sistema chama `webhook_service.send_reservation_webhook()`
9. Webhook envia dados para Make.com
10. Make.com dispara email para `employee.email` com:
    - Detalhes da reserva
    - Botão "✅ Confirmar Retirada"
    - Botão "❌ Cancelar Reserva"
11. Sistema redireciona e exibe mensagem de sucesso

### Fluxo Alternativo 8a - Falha no Webhook

8a.1. Sistema loga erro no console  
8a.2. Reserva é criada normalmente (email não enviado)  
8a.3. Continua fluxo normal

### Regras de Negócio

- **RN-13:** Reserva baixa estoque imediatamente
- **RN-14:** Email expira em 7 dias
- **RN-15:** Reserva pode ser confirmada ou cancelada via email
- **RN-16:** Após confirmação, tipo muda de RESERVA para SAIDA

---

## ✅ UC-05: Confirmar Reserva (via Email)

**Ator:** Técnico (destinatário do email)  
**Pré-condição:** Token válido e não expirado

### Fluxo Principal

1. Técnico recebe email com link de confirmação
2. Clica em "✅ Confirmar Retirada"
3. Sistema abre página de confirmação
4. Exibe detalhes da reserva
5. Técnico clica em "Confirmar"
6. Sistema valida token:
   - Token existe?
   - Não foi processado antes?
   - Não está expirado?
7. Sistema atualiza `StockOut`:
   - `movement_type = 'SAIDA'` (converte reserva em saída definitiva)
8. Sistema atualiza `ReservationToken`:
   - `confirmed = True`
   - `confirmed_at = now()`
   - `action = 'CONFIRMED'`
9. Exibe página de sucesso "✅ Reserva Confirmada"

### Fluxo Alternativo 6a - Token Inválido

6a.1. Sistema exibe "Token inválido ou não encontrado"  
6a.2. Fim do caso de uso

### Fluxo Alternativo 6b - Token Expirado

6b.1. Sistema exibe "Este link expirou. Entre em contato com o setor responsável."  
6b.2. Fim do caso de uso

### Fluxo Alternativo 6c - Token Já Processado

6c.1. Sistema exibe "Esta reserva já foi processada (ação: CONFIRMADA)"  
6c.2. Fim do caso de uso

### Regras de Negócio

- **RN-17:** Token expira em 7 dias
- **RN-18:** Token só pode ser usado uma vez
- **RN-19:** Estoque não é alterado (já foi baixado na criação)

---

## ❌ UC-06: Cancelar Reserva (via Email)

**Ator:** Técnico  
**Pré-condição:** Token válido e não expirado

### Fluxo Principal

1. Técnico recebe email com link de cancelamento
2. Clica em "❌ Cancelar Reserva"
3. Sistema abre página de cancelamento
4. Exibe detalhes da reserva
5. Técnico clica em "Cancelar"
6. Sistema valida token (igual UC-05, passo 6)
7. Sistema busca `ProductStock` e trava com `select_for_update()`
8. Sistema devolve estoque:
   - `quantity += saída.quantity`
9. Sistema atualiza `StockOut`:
   - `observation = '[CANCELADA] ' + observação original`
10. Sistema atualiza `ReservationToken`:
    - `confirmed = True`
    - `confirmed_at = now()`
    - `action = 'CANCELLED'`
11. Exibe página "❌ Reserva Cancelada - Estoque devolvido"

### Fluxo Alternativo - Mesmos de UC-05

### Regras de Negócio

- **RN-20:** Cancelamento devolve estoque imediatamente
- **RN-21:** Saída fica marcada no histórico (soft delete)

### Exemplo Prático

**Antes do Cancelamento:**
- Estoque: 45 unidades
- Reserva: 5 unidades

**Após Cancelamento:**
- Estoque: 50 unidades (5 devolvidas)
- Status da Reserva: Cancelada

---

## 🔄 UC-07: Reverter Saída de Material

**Ator:** Gestor  
**Pré-condição:** Usuário autenticado e com permissão `change_stockout`

### Fluxo Principal

1. Gestor acessa "Histórico de Movimentações"
2. Localiza saída a reverter
3. Clica em "🔙 Reverter"
4. Sistema exibe confirmação:
   - Detalhes da saída
   - Quantidade a ser devolvida
5. Gestor confirma
6. Sistema valida:
   - Saída não foi cancelada antes?
7. Sistema inicia transação atômica
8. Sistema busca `ProductStock` e trava
9. Sistema devolve estoque:
   - `quantity += saída.quantity`
10. Sistema atualiza `StockOut`:
    - `is_cancelled = True`
    - `cancelled_at = now()`
    - `cancelled_by = usuário logado`
11. Sistema commita transação
12. Redireciona para histórico
13. Exibe "✅ Saída revertida com sucesso! X unidade(s) devolvida(s)"

### Fluxo Alternativo 6a - Saída Já Cancelada

6a.1. Sistema exibe "Esta saída já foi cancelada anteriormente"  
6a.2. Redireciona para histórico  
6a.3. Fim do caso de uso

### Regras de Negócio

- **RN-22:** Reversão devolve estoque ao local original
- **RN-23:** Saída revertida fica marcada no histórico (não é deletada)
- **RN-24:** Registra quem e quando fez a reversão

---

## 👤 UC-08: Login com Microsoft SSO

**Ator:** Qualquer usuário  
**Pré-condição:** Usuário tem conta no Azure AD da empresa

### Fluxo Principal

1. Usuário acessa página de login
2. Clica em "Entrar com Microsoft"
3. Sistema redireciona para Azure AD
4. Usuário faz login no Microsoft (se não logado)
5. Azure AD solicita consentimento (primeira vez)
6. Azure AD redireciona de volta com código OAuth
7. Sistema valida código e obtém token
8. Sistema obtém dados do perfil:
   - `id` (Object ID)
   - `displayName`
   - `mail`
   - `jobTitle`
   - `department`
9. Sistema busca ou cria usuário:
   - Se `microsoft_oid` existe → Loga usuário existente
   - Se não existe → Cria novo `Employee`
10. Signal `user_logged_in` dispara
11. Sistema verifica cargo (`jobTitle`):
    - Contém "infraestrutura", "pós-vendas", etc?
    - Se sim → Adiciona ao grupo "Gestores"
    - Se não → Remove do grupo "Gestores"
12. Sistema cria sessão
13. Redireciona para dashboard

### Fluxo Alternativo 5a - Usuário Nega Consentimento

5a.1. Azure AD retorna erro  
5a.2. Sistema exibe "Não foi possível fazer login"  
5a.3. Fim do caso de uso

### Regras de Negócio

- **RN-25:** Permissões são atualizadas a cada login
- **RN-26:** Usuário pode ter login híbrido (local + SSO)
- **RN-27:** Dados do Azure AD sobrescrevem dados locais

---

## 🔍 UC-09: Consultar Estoque de Produto

**Ator:** Qualquer usuário autenticado  
**Pré-condição:** Usuário logado

### Fluxo Principal

1. Usuário acessa "Produtos"
2. Visualiza lista com todos os produtos
3. Para cada produto, vê:
   - Nome, Modelo, Fabricante
   - Estoque em Manaus
   - Estoque em São Paulo
   - Total geral
4. Usuário pode:
   - Buscar por nome/modelo/fabricante
   - Filtrar por localização
   - Ver histórico de entradas (clique em produto)

### Fluxo Alternativo 4a - Aplicar Filtro

4a.1. Usuário seleciona "Apenas Manaus"  
4a.2. Sistema filtra: `stocks__location='MAO' AND quantity > 0`  
4a.3. Exibe apenas produtos com estoque em Manaus

### Regras de Negócio

- **RN-28:** Produtos com estoque zerado aparecem na lista geral
- **RN-29:** Filtro por local só mostra produtos com estoque > 0 naquele local

---

## 📊 UC-10: Visualizar Histórico de Movimentações

**Ator:** Qualquer usuário autenticado  
**Pré-condição:** Usuário logado

### Fluxo Principal

1. Usuário acessa "Histórico"
2. Sistema exibe duas abas:
   - **Entradas:** Lista de `StockEntry` ordenada por data DESC
   - **Saídas:** Lista de `StockOut` ordenada por data DESC
3. Para cada entrada, exibe:
   - Data/hora
   - Produto
   - Tipo
   - NF
   - Local
   - Quantidade
   - Responsável
4. Para cada saída, exibe:
   - Data/hora
   - Produto
   - Tipo
   - Cliente
   - Local
   - Quantidade
   - Responsável
   - Status (Normal / Cancelada)
   - Botão "Reverter" (se for gestor e não cancelada)

### Regras de Negócio

- **RN-30:** Histórico é somente leitura para usuários padrão
- **RN-31:** Gestores podem reverter saídas
- **RN-32:** Entradas e saídas canceladas ficam visíveis no histórico

---

## 📈 Métricas e Dashboard

### Estatísticas Exibidas

1. **Total de Produtos Cadastrados**
2. **Produtos com Estoque Zerado** (alerta)
3. **Produtos Ativos** (com estoque > 0)

### Cálculo

```python
stats = {
    'total': products.count(),
    'alert': products.filter(stocks__quantity__lte=0).distinct().count(),
    'active': total - alert
}
```

---

## 🎯 Resumo de Permissões por Caso de Uso

| Caso de Uso | Gestor | Usuário Padrão |
|-------------|--------|----------------|
| UC-01: Cadastrar Produto | ✅ | ❌ |
| UC-02: Registrar Entrada | ✅ | ❌ |
| UC-03: Registrar Saída | ✅ | ❌ |
| UC-04: Criar Reserva | ✅ | ❌ |
| UC-05: Confirmar Reserva | ✅ | ✅ (via email) |
| UC-06: Cancelar Reserva | ✅ | ✅ (via email) |
| UC-07: Reverter Saída | ✅ | ❌ |
| UC-08: Login SSO | ✅ | ✅ |
| UC-09: Consultar Estoque | ✅ | ✅ |
| UC-10: Ver Histórico | ✅ | ✅ |

---

**Última atualização:** Março 2026