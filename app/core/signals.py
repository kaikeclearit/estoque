from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import StockOut, ReservationToken
from core.services.webhook_service import send_reservation_webhook

@receiver(post_save, sender=StockOut)
def send_reservation_notification(sender, instance, created, **kwargs):
    """Dispara webhook quando criar RESERVA"""
    if created and instance.movement_type == 'RESERVA':
        token = ReservationToken.objects.create(stock_out=instance)
        send_reservation_webhook(instance, token)