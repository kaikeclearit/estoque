import requests
from django.conf import settings
from django.urls import reverse

def send_reservation_webhook(stock_out, token):
    """Envia dados para Make.com webhook"""
    
    confirm_url = f"{settings.SITE_URL}{reverse('confirm_reservation', kwargs={'token': token.token})}"
    cancel_url = f"{settings.SITE_URL}{reverse('cancel_reservation', kwargs={'token': token.token})}"
    
    payload = {
        "to_email": stock_out.employee.email,
        "to_name": stock_out.employee.get_full_name() or stock_out.employee.username,
        "product_name": stock_out.product.name,
        "client_name": stock_out.client.name,
        "quantity": stock_out.quantity,
        "location": stock_out.get_location_display(),
        "reservation_date": stock_out.created_at.strftime('%d/%m/%Y'),
        "scheduled_date": stock_out.scheduled_date.strftime('%d/%m/%Y') if stock_out.scheduled_date else 'Não definida',
        "confirm_url": confirm_url,
        "cancel_url": cancel_url,
        "expires_days": 7,
        "reservation_id": stock_out.id,
    }
    
    try:
        response = requests.post(
            settings.RESERVATION_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Erro webhook: {e}")
        return False