from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from core.models import ProductStock

@login_required
def product_stock_api(request):
    """API para retornar quantidade disponível"""
    product_id = request.GET.get('product')
    location = request.GET.get('location')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        query = ProductStock.objects.filter(product_id=product_id)
        
        if location:
            query = query.filter(location=location)
            stock = query.first()
            quantity = stock.quantity if stock else None
        else:
            # Sem localidade: soma de todas
            stock = query.first()
            quantity = sum(query.values_list('quantity', flat=True)) if stock else None

        if stock:
            return JsonResponse({
                'quantity': quantity,
                'product': stock.product.name,
                'location': stock.location.name if location else 'Todas'
            })
        else:
            return JsonResponse({
                'quantity': 0,
                'message': 'Produto sem estoque'
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)