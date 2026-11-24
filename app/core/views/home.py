from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.models import active_location_choices
from core.services import stock_alerts as sa
from core.pagination import paginate


@login_required
def index(request):
    location_choices = active_location_choices()
    valid_locations = dict(location_choices)
    location = request.GET.get('local', '')
    if location not in valid_locations:
        location = ''

    all_alerts = sa.compute_stock_alerts()
    shown = [a for a in all_alerts
             if a.status != sa.STATUS_OK and (not location or a.stock.location_id == location)]

    context = {
        'location_summary': sa.summary_by_location(all_alerts),
        'alerts': paginate(request, shown),
        'location_filter': location,
        'location_choices': location_choices,
        'status_meta': sa.STATUS_META,
        'rules': {
            'window': sa.CONSUMPTION_WINDOW_DAYS,
            'critical_days': sa.CRITICAL_COVERAGE_DAYS,
            'warning_days': sa.WARNING_COVERAGE_DAYS,
            'target_days': sa.TARGET_COVERAGE_DAYS,
            'warning_factor': sa.WARNING_FACTOR,
        },
    }
    return render(request, 'core/home.html', context)
