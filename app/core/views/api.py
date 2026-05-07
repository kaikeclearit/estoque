from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from core.models import ProductStock

@login_required
def product_stock_api(request):
    """API para retornar quantidade disponível"""
    product_id = request.GET.get('product')
    location_id = request.GET.get('location')
    
    if not product_id:
        return JsonResponse({'error': 'Product ID required'}, status=400)
    
    try:
        query = ProductStock.objects.filter(product_id=product_id)
        
        if location_id:
            query = query.filter(location_id=location_id)
        
        stock = query.first()
        
        if stock:
            return JsonResponse({
                'quantity': stock.quantity,
                'product': stock.product.name,
                'location': stock.location.name if location_id else 'Todas'
            })
        else:
            return JsonResponse({
                'quantity': 0,
                'message': 'Produto sem estoque'
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)