"""
{% static_v 'core/css/clearit_theme.css' %} -> /static/core/css/clearit_theme.css?v=<data de modificação>

Garante que o navegador baixe CSS/JS de novo sempre que o arquivo mudar
(sem isso ele pode reaproveitar a versão antiga em cache e a tela "quebra").
Em produção o ManifestStaticFilesStorage já põe hash no nome; o ?v= é inofensivo.
"""
import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path):
    url = static(path)
    found = finders.find(path)
    if found and os.path.exists(found):
        return f"{url}?v={int(os.path.getmtime(found))}"
    return url
