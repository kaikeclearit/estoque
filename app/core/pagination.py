"""Paginação padrão do sistema (10 itens por página)."""
from django.core.paginator import Paginator

PER_PAGE = 10


def paginate(request, items, param='page', per_page=PER_PAGE):
    """Retorna o Page da página pedida em ?<param>=N (inválida/fora do range -> última válida)."""
    return Paginator(items, per_page).get_page(request.GET.get(param))
