"""
Carrinho de saída, guardado na sessão do usuário.

Cada item é {product_id, location, quantity}. O mesmo produto na mesma
localidade é somado numa linha só. A baixa real só acontece no checkout,
dentro de uma transação: se faltar saldo de qualquer item, nada é baixado.
"""
from django.db import transaction

from core.models import Location, Product, ProductStock, StockOut, StockOutOrder

SESSION_KEY = 'stockout_cart'


def _items(request):
    return request.session.get(SESSION_KEY, [])


def _save(request, items):
    request.session[SESSION_KEY] = items
    request.session.modified = True


def count(request):
    return len(_items(request))


def quantity_in_cart(request, product_id, location):
    return sum(i['quantity'] for i in _items(request)
               if i['product_id'] == product_id and i['location'] == location)


def available(product_id, location):
    stock = ProductStock.objects.filter(product_id=product_id, location_id=location).first()
    return stock.quantity if stock else 0


def add(request, product, location, quantity):
    """Adiciona (ou soma) um item. Retorna mensagem de erro ou None."""
    in_cart = quantity_in_cart(request, product.pk, location.code)
    free = available(product.pk, location.code) - in_cart
    if quantity > free:
        return (f'Saldo insuficiente de {product.name} em {location.code}: '
                f'disponível {max(free, 0)}' + (f' (já há {in_cart} no carrinho)' if in_cart else '') + '.')
    items = _items(request)
    for item in items:
        if item['product_id'] == product.pk and item['location'] == location.code:
            item['quantity'] += quantity
            break
    else:
        items.append({'product_id': product.pk, 'location': location.code, 'quantity': quantity})
    _save(request, items)
    return None


def remove(request, product_id, location):
    _save(request, [i for i in _items(request)
                    if not (i['product_id'] == product_id and i['location'] == location)])


def clear(request):
    _save(request, [])


def detailed(request):
    """Itens com objetos e saldo atual, descartando produtos/localidades que deixaram de existir."""
    items = _items(request)
    products = Product.objects.in_bulk([i['product_id'] for i in items])
    locations = Location.objects.filter(is_active=True).in_bulk([i['location'] for i in items])
    stocks = {(s.product_id, s.location_id): s.quantity for s in ProductStock.objects.filter(
        product_id__in=products.keys())}
    rows, valid = [], []
    for i in items:
        product, location = products.get(i['product_id']), locations.get(i['location'])
        if not product or not location:
            continue  # produto excluído ou localidade desativada depois de entrar no carrinho
        valid.append(i)
        avail = stocks.get((product.pk, location.code), 0)
        rows.append({'product': product, 'location': location, 'quantity': i['quantity'],
                     'available': avail, 'ok': i['quantity'] <= avail})
    if len(valid) != len(items):
        _save(request, valid)
    return rows


def checkout(request, *, client, movement_type, project, observation, scheduled_date, user):
    """
    Cria o pedido e um StockOut por item numa transação só.
    Lança ValueError (com a mensagem do item sem saldo) e não baixa nada se faltar estoque.
    """
    rows = detailed(request)
    if not rows:
        raise ValueError('O carrinho está vazio.')
    with transaction.atomic():
        order = StockOutOrder.objects.create(
            client=client, project=project, movement_type=movement_type,
            observation=observation, employee=user)
        for row in rows:
            StockOut(
                product=row['product'], location=row['location'], client=client,
                movement_type=movement_type, scheduled_date=scheduled_date,
                quantity=row['quantity'], employee=user, order=order,
                observation=' — '.join(filter(None, [project, observation])) or None,
            ).save()  # StockOut.save() trava o saldo e lança ValueError se faltar
    clear(request)
    return order
