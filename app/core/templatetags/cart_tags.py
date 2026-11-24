from django import template

from core.services import cart

register = template.Library()


@register.simple_tag(takes_context=True)
def cart_count(context):
    request = context.get('request')
    return cart.count(request) if request and hasattr(request, 'session') else 0
