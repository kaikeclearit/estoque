from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from core.models import ReservationToken, ProductStock

def confirm_reservation(request, token):
    """Confirma reserva"""
    reservation_token = get_object_or_404(ReservationToken, token=token)
    
    if reservation_token.confirmed:
        return render(request, 'core/reservation_already_processed.html', {
            'action': reservation_token.action,
        })
    
    if reservation_token.is_expired():
        return render(request, 'core/reservation_expired.html')
    
    if request.method == 'POST':
        stock_out = reservation_token.stock_out
        stock_out.movement_type = 'SAIDA'
        stock_out.save()
        
        reservation_token.confirmed = True
        reservation_token.confirmed_at = timezone.now()
        reservation_token.action = 'CONFIRMED'
        reservation_token.save()
        
        return render(request, 'core/reservation_confirmed.html')
    
    return render(request, 'core/confirm_reservation.html', {
        'stock_out': reservation_token.stock_out,
    })

def cancel_reservation(request, token):
    """Cancela reserva e devolve estoque"""
    reservation_token = get_object_or_404(ReservationToken, token=token)
    
    if reservation_token.confirmed:
        return render(request, 'core/reservation_already_processed.html', {
            'action': reservation_token.action,
        })
    
    if reservation_token.is_expired():
        return render(request, 'core/reservation_expired.html')
    
    if request.method == 'POST':
        stock_out = reservation_token.stock_out
        
        # Devolver estoque
        stock = ProductStock.objects.get(
            product=stock_out.product,
            location=stock_out.location
        )
        stock.quantity += stock_out.quantity
        stock.save()
        
        stock_out.observation = f"[CANCELADA] {stock_out.observation or ''}"
        stock_out.save()
        
        reservation_token.confirmed = True
        reservation_token.confirmed_at = timezone.now()
        reservation_token.action = 'CANCELLED'
        reservation_token.save()
        
        return render(request, 'core/reservation_cancelled.html')
    
    return render(request, 'core/cancel_reservation.html', {
        'stock_out': reservation_token.stock_out,
    })