"""
Perfis de acesso do sistema (cada perfil é um Group do Django).

| Perfil     | Lê | Produtos, clientes, entradas | Saídas e correções | Localidades | Usuários | Ajuste direto de saldo |
|------------|:--:|:----------------------------:|:------------------:|:-----------:|:--------:|:----------------------:|
| Admin      | ✔  |              ✔               |         ✔          |      ✔      |    ✔     |           ✔            |
| Gestor     | ✔  |              ✔               |         ✔          |      ✔      |    ✔     |           ✘            |
| Dev        | ✔  |              ✔               |         ✘          |      ✘      |    ✔     |           ✘            |
| Pós-vendas | ✔  |              ✔               |         ✘          |      ✘      |    ✘     |           ✘            |
| Pré-vendas | ✔  |              ✘               |         ✘          |      ✘      |    ✘     |           ✘            |

Usuário sem perfil fica só com leitura (mesmo comportamento do Pré-vendas).

ATENÇÃO: as permissões de cada grupo são gravadas por data migration
(a última é a 0012). Ao mudar esta tabela, crie uma nova data migration.
"""

ROLE_ADMIN = 'Admin'
ROLE_DEV = 'Dev'
ROLE_GESTOR = 'Gestor'
ROLE_POS_VENDAS = 'Pós-vendas'
ROLE_PRE_VENDAS = 'Pré-vendas'

# Ordem de exibição (e de prioridade, se alguém tiver mais de um grupo)
ROLE_NAMES = [ROLE_ADMIN, ROLE_DEV, ROLE_GESTOR, ROLE_POS_VENDAS, ROLE_PRE_VENDAS]

ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: 'Acesso total, inclusive ajuste direto de saldo',
    ROLE_DEV: 'Produtos, clientes e entradas + gerencia usuários (sem saídas)',
    ROLE_GESTOR: 'Tudo, exceto ajuste direto de saldo',
    ROLE_POS_VENDAS: 'Produtos, clientes e entradas (sem saídas)',
    ROLE_PRE_VENDAS: 'Somente leitura',
}
