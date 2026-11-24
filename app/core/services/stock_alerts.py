"""
Cálculo de alertas de estoque por produto/localidade (dashboard da tela inicial).

Regras (avaliadas nesta ordem, para cada par produto + localidade):

- EM FALTA  : saldo = 0 (e o item é controlado ali: tem mínimo definido ou teve consumo)
- CRÍTICO   : saldo <= estoque mínimo,       ou cobertura <= CRITICAL_COVERAGE_DAYS
- ATENÇÃO   : saldo <= mínimo x WARNING_FACTOR, ou cobertura <= WARNING_COVERAGE_DAYS
- OK        : demais casos

"Cobertura" = quantos dias o saldo atual dura no ritmo de consumo dos últimos
CONSUMPTION_WINDOW_DAYS dias (saídas não canceladas, de qualquer tipo).

"Sugestão de compra" = quanto falta para chegar ao maior valor entre
2x o estoque mínimo e TARGET_COVERAGE_DAYS dias de consumo.
"""
import math
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from core.models import ProductStock, StockOut, active_location_choices

CONSUMPTION_WINDOW_DAYS = 90
CRITICAL_COVERAGE_DAYS = 15
WARNING_COVERAGE_DAYS = 30
TARGET_COVERAGE_DAYS = 60
WARNING_FACTOR = 1.5

STATUS_OUT = 'FALTA'
STATUS_CRITICAL = 'CRITICO'
STATUS_WARNING = 'ATENCAO'
STATUS_OK = 'OK'

STATUS_META = {
    STATUS_OUT: {'label': 'Em falta', 'order': 0, 'color': 'danger', 'icon': 'bi-x-octagon-fill'},
    STATUS_CRITICAL: {'label': 'Crítico', 'order': 1, 'color': 'warning', 'icon': 'bi-exclamation-triangle-fill'},
    STATUS_WARNING: {'label': 'Atenção', 'order': 2, 'color': 'info', 'icon': 'bi-hourglass-split'},
    STATUS_OK: {'label': 'OK', 'order': 3, 'color': 'success', 'icon': 'bi-check-circle-fill'},
}


@dataclass
class StockAlert:
    stock: ProductStock
    status: str
    monthly_consumption: float
    coverage_days: int | None
    suggested_purchase: int

    @property
    def product(self):
        return self.stock.product

    @property
    def meta(self):
        return STATUS_META[self.status]


def _classify(qty, minimum, coverage, consumption):
    if qty <= 0:
        return STATUS_OUT if (minimum > 0 or consumption > 0) else None
    if (minimum and qty <= minimum) or (coverage is not None and coverage <= CRITICAL_COVERAGE_DAYS):
        return STATUS_CRITICAL
    if (minimum and qty <= math.ceil(minimum * WARNING_FACTOR)) or (
            coverage is not None and coverage <= WARNING_COVERAGE_DAYS):
        return STATUS_WARNING
    return STATUS_OK


def compute_stock_alerts(location=None):
    """Retorna a lista de StockAlert (inclusive OK), ordenada por gravidade."""
    since = timezone.now() - timedelta(days=CONSUMPTION_WINDOW_DAYS)
    consumption = {
        (row['product_id'], row['location']): row['total']
        for row in StockOut.objects.filter(created_at__gte=since, is_cancelled=False)
        .values('product_id', 'location').annotate(total=Sum('quantity'))
    }

    # Ignora produtos excluídos e localidades desativadas
    stocks = ProductStock.objects.select_related('product', 'location').filter(
        product__is_deleted=False, location__is_active=True)
    if location:
        stocks = stocks.filter(location_id=location)

    alerts = []
    for stock in stocks:
        used = consumption.get((stock.product_id, stock.location_id), 0) or 0
        daily = used / CONSUMPTION_WINDOW_DAYS
        coverage = int(stock.quantity / daily) if daily > 0 else None
        status = _classify(stock.quantity, stock.minimum_quantity, coverage, used)
        if status is None:
            continue
        target = max(stock.minimum_quantity * 2, math.ceil(daily * TARGET_COVERAGE_DAYS))
        alerts.append(StockAlert(
            stock=stock,
            status=status,
            monthly_consumption=round(daily * 30, 1),
            coverage_days=coverage,
            suggested_purchase=max(target - stock.quantity, 0) if status != STATUS_OK else 0,
        ))

    alerts.sort(key=lambda a: (a.meta['order'],
                               a.coverage_days if a.coverage_days is not None else 10 ** 6,
                               a.product.name))
    return alerts


def summary_by_location(alerts):
    """{'MAO': {'name': 'Manaus', 'FALTA': n, 'CRITICO': n, 'ATENCAO': n, 'OK': n, 'total': n}, ...}"""
    summary = {code: {'code': code, 'name': name, 'total': 0, **{s: 0 for s in STATUS_META}}
               for code, name in active_location_choices()}
    for a in alerts:
        loc = summary.setdefault(a.stock.location_id, {'code': a.stock.location_id, 'name': a.stock.location.name,
                                                       'total': 0, **{s: 0 for s in STATUS_META}})
        loc[a.status] += 1
        loc['total'] += 1
    return list(summary.values())
