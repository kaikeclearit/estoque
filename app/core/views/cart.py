from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import CartAddForm, CartCheckoutForm
from core.models import StockOutOrder
from core.services import cart

can_stockout = permission_required('core.add_stockout', raise_exception=True)


@login_required
@can_stockout
def cart_view(request):
    initial = {}
    if request.GET.get('product'):
        initial['product'] = request.GET['product']
    rows = cart.detailed(request)
    return render(request, 'core/stock/cart.html', {
        'add_form': CartAddForm(initial=initial),
        'checkout_form': CartCheckoutForm(),
        'rows': rows,
        'total_units': sum(r['quantity'] for r in rows),
        'has_problem': any(not r['ok'] for r in rows),
    })


@login_required
@can_stockout
@require_POST
def cart_add(request):
    form = CartAddForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        error = cart.add(request, d['product'], d['location'], d['quantity'])
        if error:
            messages.error(request, error)
        else:
            messages.success(request, f"{d['quantity']}x {d['product'].name} ({d['location'].code}) adicionado ao carrinho.")
    else:
        messages.error(request, 'Preencha produto, localidade e uma quantidade maior que zero.')
    return redirect('cart')


@login_required
@can_stockout
@require_POST
def cart_remove(request):
    try:
        cart.remove(request, int(request.POST['product_id']), request.POST['location'])
    except (KeyError, ValueError):
        pass
    return redirect('cart')


@login_required
@can_stockout
@require_POST
def cart_clear(request):
    cart.clear(request)
    messages.info(request, 'Carrinho esvaziado.')
    return redirect('cart')


@login_required
@can_stockout
@require_POST
def cart_checkout(request):
    form = CartCheckoutForm(request.POST)
    if not form.is_valid():
        rows = cart.detailed(request)
        return render(request, 'core/stock/cart.html', {
            'add_form': CartAddForm(), 'checkout_form': form, 'rows': rows,
            'total_units': sum(r['quantity'] for r in rows),
            'has_problem': any(not r['ok'] for r in rows),
        })
    d = form.cleaned_data
    try:
        order = cart.checkout(request, client=d['client'], movement_type=d['movement_type'],
                              project=d['project'], observation=d['observation'],
                              scheduled_date=d['scheduled_date'], user=request.user)
    except ValueError as e:
        messages.error(request, f'Nenhum item foi baixado. {e}')
        return redirect('cart')
    messages.success(request, f'{order} registrado: {order.items.count()} item(ns) baixado(s) do estoque.')
    return redirect('order_detail', pk=order.pk)


@login_required
def order_detail(request, pk):
    order = get_object_or_404(StockOutOrder.objects.select_related('client', 'employee'), pk=pk)
    items = order.items.select_related('product', 'location', 'cancelled_by')
    return render(request, 'core/stock/order_detail.html', {'order': order, 'items': items})
