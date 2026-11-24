from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def page_url(context, param, number, **extra):
    """
    Monta a querystring atual trocando só o parâmetro de página
    (mantém busca, filtros, aba etc.). Ex.: {% page_url 'page' 3 %} -> ?search=x&page=3
    """
    query = context['request'].GET.copy()
    query[param] = number
    for key, value in extra.items():
        query[key] = value
    return '?' + query.urlencode()
