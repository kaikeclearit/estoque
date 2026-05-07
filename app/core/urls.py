from django.urls import path
from core.views import products, home, clients, movements
from django.contrib.auth import views as auth_views
# Import para bloquear acessos
from django.contrib.auth.decorators import login_required, permission_required

# Import para reservas
from core.views import reservations 
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

    # Histórico Unificado (Abas) - Livre
    path('historico/', movements.movements_list, name='movements_list'),
    path('saida/historico/', movements.output_list, name='output_list'),
    path('entrada/historico/', movements.entry_list, name='entry_list'),

    # Reservas 
    path('reserva/confirmar/<uuid:token>/', reservations.confirm_reservation, name='confirm_reservation'),
    path('reserva/cancelar/<uuid:token>/', reservations.cancel_reservation, name='cancel_reservation'),

     # Reverter saída
    path('saida/reverter/<int:pk>/', movements.reverse_stockout, name='reverse_stockout'),

    # API para consultar estoque
    path('api/product-stock/', product_stock_api, name='product_stock_api'),

]