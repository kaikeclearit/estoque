from django.urls import path
from core.views import products, home, clients, movements, users, locations, cart
from django.contrib.auth import views as auth_views
# Import para bloquear acessos
from django.contrib.auth.decorators import login_required, permission_required

from core.views.api import product_stock_api

# --- FUNÇÃO AUXILIAR ---
# Se não tiver permissão, dá Erro 403 (Proibido) em vez de redirecionar pro login.
def gestor_only(perm):
    return permission_required(f'core.{perm}', raise_exception=True)

urlpatterns = [
    # AUTH
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # HOME
    path('', home.index, name='home'),

    # --- PRODUTOS ---
    # Agora 'produtos/' carrega direto a LISTA (Dashboard), matamos o menu antigo.
    path('produtos/', products.product_list, name='product_list'), 
    
    # Ações Restritas (Só Gestor)
    path('produtos/novo/', gestor_only('add_product')(products.product_create), name='product_create'),
    path('produtos/editar/<int:pk>/', gestor_only('change_product')(products.product_update), name='product_update'),
    path('produtos/excluir/<int:pk>/', gestor_only('delete_product')(products.delete_product), name='delete_product'),
    path('produtos/ajustar-saldo/<int:pk>/', products.adjust_stock, name='adjust_stock'),  # só Admin
    
    # Leitura (Livre)
    path('produtos/<int:pk>/historico-entradas/', products.product_entries_modal, name='product_entries_modal'),

    # --- CLIENTES ---
    # Lista (Livre)
    path('clientes/', clients.client_list, name='client_list'),
    
    # Ações Restritas (Só Gestor)
    path('clientes/novo/', gestor_only('add_client')(clients.client_create), name='client_create'),
    path('clientes/editar/<int:pk>/', gestor_only('change_client')(clients.client_update), name='client_update'),
    
    # Leitura (Livre)
    path('clientes/<int:pk>/historico/', clients.client_history_modal, name='client_history_modal'),

    # --- MOVIMENTAÇÕES ---
    # Ações Restritas (Só Gestor)
    path('entrada/nova/', gestor_only('add_stockentry')(movements.entry_create), name='entry_create'),
    path('saida/nova/', gestor_only('add_stockout')(movements.output_create), name='output_create'),

    # Carrinho de saída (vários itens num pedido só)
    path('saida/carrinho/', cart.cart_view, name='cart'),
    path('saida/carrinho/adicionar/', cart.cart_add, name='cart_add'),
    path('saida/carrinho/remover/', cart.cart_remove, name='cart_remove'),
    path('saida/carrinho/esvaziar/', cart.cart_clear, name='cart_clear'),
    path('saida/carrinho/finalizar/', cart.cart_checkout, name='cart_checkout'),
    path('saida/pedido/<int:pk>/', cart.order_detail, name='order_detail'),

    # Histórico Unificado (Abas) - Livre
    path('historico/', movements.movements_list, name='movements_list'),
    path('saida/historico/', movements.output_list, name='output_list'),
    path('entrada/historico/', movements.entry_list, name='entry_list'),


     # Reverter saída
    path('saida/reverter/<int:pk>/', movements.reverse_stockout, name='reverse_stockout'),

    # --- LOCALIDADES (Admin e Gestor) ---
    path('localidades/', locations.location_list, name='location_list'),
    path('localidades/nova/', locations.location_create, name='location_create'),
    path('localidades/editar/<str:pk>/', locations.location_update, name='location_update'),

    # --- USUÁRIOS (Admin, Dev e Gestor) ---
    path('usuarios/', users.user_list, name='user_list'),
    path('usuarios/novo/', users.user_create, name='user_create'),
    path('usuarios/editar/<int:pk>/', users.user_update, name='user_update'),

    # API para consultar estoque
    path('api/product-stock/', product_stock_api, name='product_stock_api'),

]