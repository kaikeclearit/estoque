"""
Importa o cadastro de produtos e o SALDO INICIAL a partir da planilha
"ESTOQUE-CLEARIT-organizado.xlsx" (aba CADASTRO).

Para cada produto da aba CADASTRO:
- cria o Produto (nome, modelo, fabricante, ID);
- para cada localidade com saldo > 0 (colunas "SALDO MAO", "SALDO SP"...),
  lança uma Entrada do tipo "Ajuste de Inventário", que gera o saldo.
O histórico antigo de entradas/saídas NÃO é importado (fica na planilha).

Regras:
- "--" / "-" / vazio em MODELO e ID viram vazio.
- ID repetido: o primeiro produto fica com o ID, os seguintes entram sem ID
  (aviso no relatório).
- Recusa rodar se já existir qualquer produto no banco (evita duplicar).
- Tudo numa transação: ou importa tudo, ou nada.

Uso (a planilha pode vir pelo stdin com "-", sem copiar para o container):
    python manage.py importar_saldo_inicial planilha.xlsx --usuario admin --dry-run
    docker compose exec -T web python manage.py importar_saldo_inicial - \\
        --usuario admin --dry-run < ESTOQUE-CLEARIT-organizado.xlsx
"""
import io
import sys
import warnings
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Location, Product, ProductStock, StockEntry

VAZIOS = {'', '-', '--', '—'}
SHEET = 'CADASTRO'


def _texto(v):
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s in VAZIOS else s


def _inteiro(v, onde):
    if v is None or (isinstance(v, str) and v.strip() in VAZIOS):
        return 0
    if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
        raise CommandError(f'{onde}: quantidade inválida {v!r}')
    return int(v)


class Command(BaseCommand):
    help = 'Importa produtos e saldo inicial da aba CADASTRO da planilha de estoque.'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', help='Caminho do .xlsx, ou "-" para ler do stdin.')
        parser.add_argument('--usuario', required=True,
                            help='Login do usuário que fica como responsável pelas entradas.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula tudo (inclusive gravação) e desfaz no fim.')

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError('openpyxl não instalado (pip install openpyxl).') from exc

        dados = sys.stdin.buffer.read() if opts['arquivo'] == '-' else open(opts['arquivo'], 'rb').read()
        if not dados:
            raise CommandError('Planilha vazia (nada recebido).')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')  # "Data Validation extension is not supported"
            wb = openpyxl.load_workbook(io.BytesIO(dados), data_only=True, read_only=True)
        if SHEET not in wb.sheetnames:
            raise CommandError(f'Aba "{SHEET}" não encontrada. Abas: {wb.sheetnames}')

        produtos, avisos = self._ler_cadastro(wb[SHEET])

        User = get_user_model()
        try:
            usuario = User.objects.get(username=opts['usuario'])
        except User.DoesNotExist as exc:
            raise CommandError(f'Usuário "{opts["usuario"]}" não existe.') from exc

        locais = sorted({loc for p in produtos for loc in p['saldos']})
        existentes = set(Location.objects.filter(code__in=locais).values_list('code', flat=True))
        faltando = [loc for loc in locais if loc not in existentes]
        if faltando:
            raise CommandError(f'Localidades não cadastradas no sistema: {faltando}')

        if Product.all_objects.exists():
            raise CommandError(
                f'Já existem {Product.all_objects.count()} produtos no banco. '
                'Esta importação é só para banco sem produtos.')

        totais = Counter()
        with transaction.atomic():
            for p in produtos:
                prod = Product.objects.create(
                    name=p['nome'], model=p['modelo'], manufacturer=p['fabricante'],
                    product_id=p['id'] or None,
                )
                for loc, qtd in p['saldos'].items():
                    if qtd > 0:
                        StockEntry.objects.create(
                            product=prod, location_id=loc, quantity=qtd,
                            entry_type='AJUSTE', nf_number='', employee=usuario,
                        )
                        totais[loc] += qtd

            # Conferência: saldo gravado == planilha
            gravado = Counter()
            for s in ProductStock.objects.filter(product__in=Product.objects.all()):
                gravado[s.location_id] += s.quantity
            if gravado != totais:
                raise CommandError(f'Conferência falhou: gravado {dict(gravado)} x planilha {dict(totais)}')

            if opts['dry_run']:
                transaction.set_rollback(True)

        self._relatorio(produtos, totais, avisos, opts['dry_run'])

    def _ler_cadastro(self, ws):
        linhas = ws.iter_rows(values_only=True)
        cab = None
        for n, row in enumerate(linhas, start=1):
            nomes = [_texto(c).upper() for c in row]
            if 'PRODUTO' in nomes:
                cab = {nome: i for i, nome in enumerate(nomes) if nome}
                cab_nomes = nomes
                inicio = n + 1
                break
        if not cab:
            raise CommandError('Cabeçalho com a coluna "PRODUTO" não encontrado na aba CADASTRO.')
        for obrig in ('PRODUTO', 'MODELO', 'ID', 'FABRICANTE'):
            if obrig not in cab:
                raise CommandError(f'Coluna "{obrig}" não encontrada no cabeçalho.')
        col_saldo = {nome.split(' ', 1)[1]: i for nome, i in cab.items()
                     if nome.startswith('SALDO ') and len(nome.split(' ', 1)[1]) <= 10}
        if not col_saldo:
            raise CommandError('Nenhuma coluna "SALDO <LOCAL>" encontrada.')
        col_total = cab.get('TOTAL')

        produtos, avisos, ids_vistos, nomes_vistos = [], [], {}, set()
        for n, row in enumerate(linhas, start=inicio):
            row = tuple(row) + (None,) * (len(cab_nomes) - len(row))
            nome = _texto(row[cab['PRODUTO']])
            if not nome:
                continue
            onde = f'linha {n} ({nome})'
            if nome in nomes_vistos:
                raise CommandError(f'{onde}: produto repetido na planilha.')
            nomes_vistos.add(nome)

            pid = _texto(row[cab['ID']])
            if pid and pid in ids_vistos:
                avisos.append(f'{onde}: ID {pid} já usado por "{ids_vistos[pid]}"; importado SEM ID.')
                pid = ''
            elif pid:
                ids_vistos[pid] = nome

            saldos = {loc: _inteiro(row[i], f'{onde} SALDO {loc}') for loc, i in col_saldo.items()}
            for loc, q in saldos.items():
                if q < 0:
                    raise CommandError(f'{onde}: saldo negativo em {loc} ({q}).')
            if col_total is not None:
                total = _inteiro(row[col_total], f'{onde} TOTAL')
                if total != sum(saldos.values()):
                    raise CommandError(f'{onde}: TOTAL {total} diferente da soma dos saldos {saldos}.')

            for i_obs, rotulo in ((cab.get('OBSERVAÇÃO MAO'), 'MAO'), (cab.get('OBSERVAÇÃO SP'), 'SP')):
                if i_obs is not None and _texto(row[i_obs]):
                    avisos.append(f'{onde}: observação {rotulo} não importada: "{_texto(row[i_obs])}"')

            produtos.append({
                'nome': nome,
                'modelo': _texto(row[cab['MODELO']]),
                'fabricante': _texto(row[cab['FABRICANTE']]),
                'id': pid,
                'saldos': saldos,
            })
        if not produtos:
            raise CommandError('Nenhum produto encontrado na aba CADASTRO.')
        return produtos, avisos

    def _relatorio(self, produtos, totais, avisos, dry_run):
        w = self.stdout.write
        com_saldo = sum(1 for p in produtos if any(q > 0 for q in p['saldos'].values()))
        w(f'Produtos: {len(produtos)} ({com_saldo} com saldo, {len(produtos) - com_saldo} zerados)')
        for loc in sorted(totais):
            n = sum(1 for p in produtos if p['saldos'].get(loc, 0) > 0)
            w(f'  {loc}: {n} produtos, {totais[loc]} itens')
        w(f'  Total: {sum(totais.values())} itens')
        for a in avisos:
            w(self.style.WARNING(f'AVISO: {a}'))
        if dry_run:
            w(self.style.WARNING('DRY-RUN: nada foi gravado (tudo desfeito).'))
        else:
            w(self.style.SUCCESS('Importação concluída.'))
