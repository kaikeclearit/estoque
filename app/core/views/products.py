from django.shortcuts import render, redirect, get_object_or_404
from core.models import Product, StockEntry
from core.forms import ProductForm
from django.contrib.auth.decorators import login_required
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
    if location_filter == 'MAO':
        # Mostrar APENAS produtos que TÊM estoque em Manaus (quantidade > 0)
        products = products.filter(
            stocks__location='MAO',
            stocks__quantity__gt=0
        ).distinct()
    elif location_filter == 'SP':
        # Mostrar APENAS produtos que TÊM estoque em São Paulo (quantidade > 0)
        products = products.filter(
            stocks__location='SP',
            stocks__quantity__gt=0
        ).distinct()
    # Se for 'TODOS', não aplica filtro

    # Prefetch stocks para otimizar queries
    products = products.prefetch_related('stocks')

    # --- MÉTRICAS PARA O DASHBOARD ---
    total_products = products.count()
    
    # Produtos com estoque zerado
    out_of_stock = products.filter(stocks__quantity__lte=0).distinct().count()
    
    context = {
        'products': products,
        'search_query': search_query,
        'location_filter': location_filter,
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

# 4. DELETE (Deletar)
@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return redirect('product_list')

@login_required
def product_menu(request):
    return render(request, 'core/products/menu.html')

def product_entries_modal(request, pk):
    product = get_object_or_404(Product, pk=pk)
    entries = StockEntry.objects.filter(product=product).order_by('-created_at')
    
    # O ERRO ESTÁ AQUI: Você está mandando só as entradas, falta o produto!
    context = {
        'entries': entries,
        'product': product,
    }
    return render(request, 'core/products/_entries_modal_content.html', context)