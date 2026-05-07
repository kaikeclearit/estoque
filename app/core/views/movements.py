from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from core.models import StockEntry, StockOut, ProductStock, Product, Client, Employee
from core.forms import StockEntryForm, StockOutForm

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
    entries = StockEntry.objects.select_related('product', 'employee').order_by('-created_at')
    context = {
        'entries': entries,
        'title': 'Histórico de Entradas'
    }
    return render(request, 'core/stock/entry_list.html', context)


# ============================================
# SAÍDAS
# ============================================

@login_required
@permission_required('core.add_stockout', raise_exception=True)
def output_create(request):
    initial_data = {}
    product_id = request.GET.get('product_id')
    
    if product_id:
        initial_data['product'] = product_id

    if request.method == 'POST':
        form = StockOutForm(request.POST)
        if form.is_valid():
            try:
                out = form.save(commit=False)
                out.employee = request.user
                out.save()  # ⭐ O save() do model tem select_for_update() - protegido!
                
                messages.success(request, 'Saída registrada com sucesso!')
                return redirect('product_list')
                
            except ValueError as e:
                # ⭐ CAPTURA O ERRO DE ESTOQUE INSUFICIENTE
                messages.error(request, str(e))
                # Reexibir o formulário com os dados preenchidos
                return render(request, 'core/stock/form.html', {
                    'form': form,
                    'title': 'Registrar Saída de Material',
                    'btn_class': 'btn-danger',
                    'icon': 'bi-box-arrow-up'
                })
            except Exception as e:
                messages.error(request, f'Erro inesperado: {str(e)}')
                return render(request, 'core/stock/form.html', {
                    'form': form,
                    'title': 'Registrar Saída de Material',
                    'btn_class': 'btn-danger',
                    'icon': 'bi-box-arrow-up'
                })
    else:
        form = StockOutForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Registrar Saída de Material',
        'btn_class': 'btn-danger',
        'icon': 'bi-box-arrow-up'
    }
    return render(request, 'core/stock/form.html', context)


@login_required
def output_list(request):
    outputs = StockOut.objects.select_related('product', 'client', 'employee').order_by('-created_at')
    
    context = {
        'outputs': outputs,
        'title': 'Histórico de Saídas'
    }
    return render(request, 'core/stock/output_list.html', context)


# ============================================
# MOVIMENTAÇÕES (AMBAS)
# ============================================

@login_required
def movements_list(request):
    entries = StockEntry.objects.select_related('product', 'employee').order_by('-created_at')
    outputs = StockOut.objects.select_related('product', 'client', 'employee').order_by('-created_at')
    
    context = {
        'entries': entries,
        'outputs': outputs,
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
                f'de {stock_out.product.name} devolvida(s) ao estoque de {stock_out.get_location_display()}.'
            )
        except ProductStock.DoesNotExist:
            messages.error(request, 'Erro: Registro de estoque não encontrado.')
        except Exception as e:
            messages.error(request, f'Erro ao reverter saída: {str(e)}')
        
        return redirect('movements_list')
    
    return render(request, 'core/stock/confirm_reverse.html', {
        'stock_out': stock_out,
    })

