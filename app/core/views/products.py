from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from core.models import Product, ProductStock, StockAdjustment, StockEntry, active_location_choices
from core.forms import ProductForm, StockAdjustmentForm
from core.pagination import paginate
from django.db.models import Q, Sum, F

# 1. READ (Listar)
@login_required
def product_list(request):
    search_query = request.GET.get('search', '')
    location_filter = request.GET.get('location', 'TODOS')
    
    # Base Query
    products = Product.objects.all().order_by('name')

    # Filtro de Busca
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(model__icontains=search_query) |
            Q(manufacturer__icontains=search_query)
        )

    # Filtro de Localização - CORRIGIDO
    location_choices = active_location_choices()
    if location_filter in dict(location_choices):
        # Mostrar APENAS produtos que TÊM estoque na localidade (quantidade > 0)
        products = products.filter(
            stocks__location_id=location_filter,
            stocks__quantity__gt=0
        ).distinct()
    else:
        location_filter = 'TODOS'

    # Prefetch stocks para otimizar queries
    products = products.prefetch_related('stocks')

    # --- MÉTRICAS PARA O DASHBOARD ---
    total_products = products.count()
    
    # Produtos com estoque zerado
    out_of_stock = products.filter(stocks__quantity__lte=0).distinct().count()
    
    page_obj = paginate(request, products)

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'location_filter': location_filter,
        'location_choices': location_choices,
        'stats': {
            'total': total_products,
            'alert': out_of_stock,
            'active': total_products - out_of_stock
        }
    }
    return render(request, 'core/products/list.html', context)


# 2. CREATE (Criar)
@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product_list') # Volta pra lista
    else:
        form = ProductForm() # Formulário vazio
    
    return render(request, 'core/products/form.html', {'form': form, 'title': 'Novo Produto'})

# 3. UPDATE (Editar)
@login_required
def product_update(request, pk):
    # Busca o produto ou dá erro 404 se não existir
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        # Carrega o form COM os dados do produto preenchidos
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        # Mostra o form preenchido para edição
        form = ProductForm(instance=product)
    
    return render(request, 'core/products/form.html', {'form': form, 'title': f'Editar {product.name}'})

# 4. DELETE (exclusão lógica: o histórico de entradas/saídas é mantido)
@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.soft_delete(request.user)
        messages.success(request, f'Produto "{product.name}" excluído. O histórico de movimentações foi mantido.')
        return redirect('product_list')
    return render(request, 'core/products/confirm_delete.html', {
        'product': product,
        'stocks': product.stocks.select_related('location').filter(quantity__gt=0),
        'outputs_count': product.stockout_set.count(),
        'entries_count': product.stockentry_set.count(),
    })


# 5. AJUSTE DIRETO DE SALDO (só Admin) — grava auditoria em StockAdjustment
@login_required
@permission_required('core.set_stock_quantity', raise_exception=True)
def adjust_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = StockAdjustmentForm(request.POST or None, product=product)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            for loc, _, new in form.changes():
                stock, _ = ProductStock.objects.select_for_update().get_or_create(
                    product=product, location=loc, defaults={'quantity': 0})
                old = stock.quantity  # relido com trava: vale o saldo real no momento
                if old == new:
                    continue
                stock.quantity = new
                stock.save(update_fields=['quantity'])
                StockAdjustment.objects.create(
                    product=product, location=loc, old_quantity=old, new_quantity=new,
                    reason=form.cleaned_data['reason'], employee=request.user)
        messages.success(request, f'Saldo de "{product.name}" ajustado.')
        return redirect('product_list')
    return render(request, 'core/products/adjust_stock.html', {
        'form': form, 'product': product,
        'qty_fields': [form[f'qty_{loc.code}'] for loc in form.locations],
        'history': product.adjustments.select_related('employee', 'location')[:10],
    })

@login_required
def product_menu(request):
    return render(request, 'core/products/menu.html')

@login_required
def product_entries_modal(request, pk):
    product = get_object_or_404(Product, pk=pk)
    entries = StockEntry.objects.filter(product=product).order_by('-created_at')
    
    # O ERRO ESTÁ AQUI: Você está mandando só as entradas, falta o produto!
    context = {
        'entries': entries,
        'product': product,
    }
    return render(request, 'core/products/_entries_modal_content.html', context)