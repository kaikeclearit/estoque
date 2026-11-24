"""
Gera dados FAKE para validar o sistema localmente (produtos, clientes,
entradas e saídas dos últimos 90 dias em MAO, SP e BSB), já distribuídos
entre os status do painel: em falta, crítico, atenção e OK.

Uso:
    python manage.py seed_demo           # cria os dados de demonstração
    python manage.py seed_demo --reset   # apaga os dados de demo e recria

Só roda com DEBUG=True, para nunca ser executado em produção por engano.
Os produtos fake têm o ID "DEMO-xxx" e os clientes começam com "[DEMO]".
"""
import math
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Client, Location, Product, ProductStock, StockAdjustment, StockEntry, StockOut

PRODUCTS = [
    # nome, modelo, fabricante
    ('Notebook', 'Latitude 5440', 'Dell'),
    ('Notebook', 'ThinkPad E14 Gen 5', 'Lenovo'),
    ('Monitor 24"', 'P2422H', 'Dell'),
    ('Mouse USB', 'M90', 'Lenovo'),
    ('Teclado USB ABNT2', 'KB216', 'Dell'),
    ('Headset USB', 'H390', 'Logitech'),
    ('Webcam Full HD', 'C920', 'Logitech'),
    ('Switch 24 portas PoE', 'CBS350-24P', 'Cisco'),
    ('Switch 48 portas', 'Aruba 6100', 'HPE Aruba'),
    ('Access Point Wi-Fi 6', 'AP-505', 'HPE Aruba'),
    ('Firewall', 'FortiGate 60F', 'Fortinet'),
    ('Transceiver SFP+ 10G', 'SFP-10G-SR', 'Fortinet'),
    ('Patch cord Cat6 1,5m', 'CAT6-1.5', 'Furukawa'),
    ('Patch cord Cat6 3m', 'CAT6-3.0', 'Furukawa'),
    ('Cabo HDMI 2m', 'HDMI-2.0', 'Multilaser'),
    ('Nobreak 1,5 kVA', 'SMS Net 4+', 'SMS'),
    ('SSD 480GB', 'A400', 'Kingston'),
    ('Memória 16GB DDR4', 'KVR32S22', 'Kingston'),
    ('Dockstation USB-C', 'WD19S', 'Dell'),
    ('Fonte notebook 65W USB-C', 'ADP-65', 'Lenovo'),
    ('Toner', 'CF258A', 'HP'),
    ('Rack 12U', 'Parede 12U', 'Triunfo'),
]

CLIENTS = [
    '[DEMO] Secretaria de Saúde', '[DEMO] Secretaria de Educação', '[DEMO] Tribunal - Comarca Central',
    '[DEMO] Prefeitura - TI', '[DEMO] Hospital Regional', '[DEMO] Interno - Suporte',
    '[DEMO] Interno - Projetos', '[DEMO] Universidade Federal',
]

LOCATIONS = ['MAO', 'SP', 'BSB']
# Mistura de cenários por localidade (pesos): falta, crítico, atenção, ok, nao_controla
SCENARIO_WEIGHTS = {
    'MAO': [2, 3, 3, 6, 2],
    'SP': [1, 2, 3, 8, 2],
    'BSB': [3, 3, 2, 4, 3],
}
SCENARIOS = ['falta', 'critico', 'atencao', 'ok', 'nao_controla']


class Command(BaseCommand):
    help = 'Gera dados fake de estoque para validação local (somente DEBUG=True).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Apaga os dados de demo antes de criar.')
        parser.add_argument('--seed', type=int, default=42, help='Semente aleatória (resultado reproduzível).')

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError('seed_demo só pode rodar com DEBUG=True (nunca em produção).')

        if opts['reset']:
            with transaction.atomic():
                demo = Product.all_objects.filter(product_id__startswith='DEMO-')
                StockOut.objects.filter(product__in=demo).delete()
                StockEntry.objects.filter(product__in=demo).delete()
                StockAdjustment.objects.filter(product__in=demo).delete()
                n, _ = demo.delete()
                Client.objects.filter(name__startswith='[DEMO]').delete()
            self.stdout.write(f'Dados de demo anteriores removidos ({n} registros).')
        elif Product.all_objects.filter(product_id__startswith='DEMO-').exists():
            raise CommandError('Já existem dados de demo. Use --reset para recriar.')

        rnd = random.Random(opts['seed'])
        now = timezone.now()
        employee = self._employee()
        clients = [Client.objects.get_or_create(name=n)[0] for n in CLIENTS]

        for code, name in [('MAO', 'Manaus'), ('SP', 'São Paulo'), ('BSB', 'Brasília')]:
            Location.objects.get_or_create(code=code, defaults={'name': name})

        counts = {s: 0 for s in SCENARIOS}
        for i, (name, model, maker) in enumerate(PRODUCTS, start=1):
            product = Product.objects.create(name=name, model=model, manufacturer=maker,
                                             product_id=f'DEMO-{i:03d}')
            for loc in LOCATIONS:
                scenario = rnd.choices(SCENARIOS, weights=SCENARIO_WEIGHTS[loc])[0]
                counts[scenario] += 1
                self._build(product, loc, scenario, rnd, now, employee, clients)

        self.stdout.write(self.style.SUCCESS(
            f'{len(PRODUCTS)} produtos e {len(clients)} clientes de demo criados. '
            f'Cenários: {counts}'))

    def _employee(self):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).order_by('id').first()
        if not user:
            user, _ = User.objects.get_or_create(username='demo', defaults={'first_name': 'Demo'})
        return user

    def _build(self, product, loc, scenario, rnd, now, employee, clients):
        if scenario == 'nao_controla':
            return

        monthly = rnd.randint(3, 25)            # consumo/mês
        consumed = monthly * 3                  # total consumido em 90 dias
        if scenario == 'falta':
            final_qty, minimum = 0, max(2, math.ceil(monthly / 2))
        elif scenario == 'critico':
            final_qty = max(1, round(monthly * rnd.uniform(0.2, 0.45)))   # ~6–13 dias
            minimum = final_qty + rnd.randint(0, 3)
        elif scenario == 'atencao':
            final_qty = max(2, round(monthly * rnd.uniform(0.6, 0.95)))  # ~18–28 dias
            minimum = max(1, math.ceil(final_qty / 1.4))
        else:  # ok
            final_qty = round(monthly * rnd.uniform(2.5, 5))             # 75–150 dias
            minimum = max(1, math.ceil(monthly / 2))

        # Entrada(s) de compra ~95 dias atrás + uma reposição no meio do período
        first = consumed + final_qty
        restock = rnd.randint(0, first // 3) if first > 6 else 0
        self._entry(product, loc, first - restock, now - timedelta(days=rnd.randint(92, 100)), employee, rnd)
        if restock:
            self._entry(product, loc, restock, now - timedelta(days=rnd.randint(40, 50)), employee, rnd)

        # Saídas espalhadas nos últimos 90 dias (em ordem cronológica)
        remaining = consumed
        days = sorted(rnd.sample(range(1, 90), k=min(rnd.randint(4, 10), consumed)), reverse=True)
        for idx, d in enumerate(days):
            qty = remaining if idx == len(days) - 1 else rnd.randint(1, max(1, remaining - (len(days) - idx - 1)))
            qty = min(qty, remaining - (len(days) - idx - 1))
            if qty <= 0:
                continue
            remaining -= qty
            out = StockOut.objects.create(
                product=product, location_id=loc, client=rnd.choice(clients), employee=employee,
                quantity=qty, movement_type=rnd.choices(['SAIDA', 'EMPRESTIMO', 'DESCARTE'], [8, 2, 1])[0],
                observation='Dado fake (seed_demo)',
            )
            StockOut.objects.filter(pk=out.pk).update(created_at=now - timedelta(days=d, hours=rnd.randint(0, 9)))

        ProductStock.objects.filter(product=product, location_id=loc).update(minimum_quantity=minimum)

    def _entry(self, product, loc, qty, when, employee, rnd):
        if qty <= 0:
            return
        entry = StockEntry.objects.create(
            product=product, location_id=loc, quantity=qty, entry_type='COMPRA',
            nf_number=f'NF-{rnd.randint(10000, 99999)}', employee=employee,
        )
        StockEntry.objects.filter(pk=entry.pk).update(created_at=when)
