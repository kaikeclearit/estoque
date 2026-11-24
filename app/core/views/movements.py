from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from core.models import StockAdjustment, StockEntry, StockOut, ProductStock, Product, Client, Employee
from django.urls import reverse
from core.forms import StockEntryForm
from core.pagination import paginate

# ============================================
# ENTRADAS
# ============================================

@login_required
@permission_required('core.add_stockentry', raise_exception=True)
def entry_create(request):
    initial_data = {}
    product_id = request.GET.get('product_id')
    
    if product_id:
        initial_data['product'] = product_id

    if request.method == 'POST':
        form = StockEntryForm(request.POST)
        if form.is_valid():
            try:
                entry = form.save(commit=False)
                entry.employee = request.user
                entry.save()  # ⭐ O save() do model já tem proteção com transaction.atomic

                messages.success(request, 'Entrada registrada com sucesso!')
                return redirect('product_list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar entrada: {str(e)}')
    else:
        form = StockEntryForm(initial=initial_data)

    context = {
        'form': form,
        'title': 'Registrar Entrada de Material',
        'btn_class': 'btn-success', 
        'icon': 'bi-box-arrow-in-down'
    }
    return render(request, 'core/stock/form.html', context)


@login_required
def entry_list(request):
    entries = StockEntry.objects.select_related('product', 'employee', 'location').order_by('-created_at')
    entries = paginate(request, entries)
    context = {
        'entries': entries,
        'page_obj': entries,
        'title': 'Histórico de Entradas'
    }
    return render(request, 'core/stock/entry_list.html', context)


# ============================================
# SAÍDAS
# ============================================

@login_required
@permission_required('core.add_stockout', raise_exception=True)
def output_create(request):
    """Saída agora é sempre pelo carrinho (1 ou vários itens). Mantém a URL antiga funcionando."""
    url = reverse('cart')
    if request.GET.get('product_id'):
        url += f"?product={request.GET['product_id']}"
    return redirect(url)


@login_required
def output_list(request):
    outputs = StockOut.objects.select_related('product', 'client', 'employee', 'location').order_by('-created_at')
    
    outputs = paginate(request, outputs)
    context = {
        'outputs': outputs,
        'page_obj': outputs,
        'title': 'Histórico de Saídas'
    }
    return render(request, 'core/stock/output_list.html', context)


# ============================================
# MOVIMENTAÇÕES (AMBAS)
# ============================================

@login_required
def movements_list(request):
    entries = StockEntry.objects.select_related('product', 'employee', 'location').order_by('-created_at')
    outputs = StockOut.objects.select_related('product', 'client', 'employee', 'location', 'cancelled_by').order_by('-created_at')
    adjustments = StockAdjustment.objects.select_related('product', 'employee', 'location')

    # Cada aba tem sua própria paginação; ?tab= mantém a aba aberta ao trocar de página
    tab = request.GET.get('tab', 'saidas')
    if tab not in ('saidas', 'entradas', 'ajustes'):
        tab = 'saidas'
    context = {
        'entries': paginate(request, entries, 'page_in'),
        'outputs': paginate(request, outputs, 'page_out'),
        'adjustments': paginate(request, adjustments, 'page_adj'),
        'tab': tab,
    }
    return render(request, 'core/stock/movements_list.html', context)


# ============================================
# REVERTER SAÍDA
# ============================================

@login_required
@permission_required('core.change_stockout', raise_exception=True)
def reverse_stockout(request, pk):
    """Reverte uma saída e devolve o estoque"""
    
    stock_out = get_object_or_404(StockOut, pk=pk)
    
    if stock_out.is_cancelled:
        messages.warning(request, 'Esta saída já foi cancelada anteriormente.')
        return redirect('movements_list')
    
    if request.method == 'POST':
        try:
            # ⭐ USAR TRANSAÇÃO ATÔMICA TAMBÉM NA REVERSÃO
            with transaction.atomic():
                # Travar o registro de estoque
                stock = ProductStock.objects.select_for_update().get(
                    product=stock_out.product,
                    location=stock_out.location
                )
                
                # Devolver estoque
                stock.quantity += stock_out.quantity
                stock.save()
                
                # Marcar como cancelada
                stock_out.is_cancelled = True
                stock_out.cancelled_at = timezone.now()
                stock_out.cancelled_by = request.user
                stock_out.save()
            
            messages.success(
                request, 
                f'Saída revertida com sucesso! {stock_out.quantity} unidade(s) '
                f'de {stock_out.product.name} devolvida(s) ao estoque de {stock_out.location.name}.'
            )
        except ProductStock.DoesNotExist:
            messages.error(request, 'Erro: Registro de estoque não encontrado.')
        except Exception as e:
            messages.error(request, f'Erro ao reverter saída: {str(e)}')
        
        return redirect('movements_list')
    
    return render(request, 'core/stock/confirm_reverse.html', {
        'stock_out': stock_out,
    })

