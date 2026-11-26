"""
Importa os CLIENTES a partir de uma ou mais planilhas de estoque
(ex.: "ESTOQUE-CLEARIT-organizado.xlsx" e a planilha geral antiga).

De cada planilha lê:
- aba CLIENTES: a linha de cabeçalho com os nomes dos clientes
  (a coluna "PRODUTO", se existir, é ignorada);
- aba SAÍDA: a coluna "CLIENTE" de todas as saídas.

Regras:
- Espaços extras são removidos; "-" / "--" / vazio são ignorados.
- Nomes de teste (contendo "TESTE", ou "CLIENTE NOVO") são ignorados,
  assim como qualquer nome passado em --ignorar.
- Comparação sem diferenciar maiúsculas/minúsculas: se o cliente já existe
  no sistema (ou aparece repetido nas planilhas), não é criado de novo.
  Por isso pode ser rodado mais de uma vez sem duplicar.
- Tudo numa transação: ou importa tudo, ou nada.

Uso (a planilha pode vir pelo stdin com "-", sem copiar para o container):
    python manage.py importar_clientes organizado.xlsx geral.xlsx --dry-run
    docker compose exec -T web python manage.py importar_clientes - \\
        --dry-run < ESTOQUE-CLEARIT-organizado.xlsx
"""
import io
import re
import sys
import warnings

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Client

VAZIOS = {'', '-', '--', '—'}
ABA_CLIENTES = 'CLIENTES'
ABA_SAIDA = 'SAÍDA'
PADRAO_TESTE = re.compile(r'TESTE|^CLIENTE NOVO$', re.IGNORECASE)


def _nome(v):
    if v is None:
        return ''
    s = re.sub(r'\s+', ' ', str(v)).strip()
    return '' if s in VAZIOS else s


class Command(BaseCommand):
    help = 'Importa clientes das abas CLIENTES e SAÍDA de uma ou mais planilhas de estoque.'

    def add_arguments(self, parser):
        parser.add_argument('arquivos', nargs='+',
                            help='Caminho(s) do .xlsx, ou "-" para ler um arquivo do stdin.')
        parser.add_argument('--ignorar', action='append', default=[], metavar='NOME',
                            help='Nome de cliente a não importar (pode repetir).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula tudo (inclusive gravação) e desfaz no fim.')

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError('openpyxl não instalado (pip install openpyxl).') from exc

        if opts['arquivos'].count('-') > 1:
            raise CommandError('Só um arquivo pode vir pelo stdin ("-").')

        ignorar = {n.upper() for n in map(_nome, opts['ignorar']) if n}
        encontrados = {}   # chave maiúscula -> grafia da primeira ocorrência
        origem = {}        # chave -> onde apareceu primeiro
        ignorados = set()

        for arquivo in opts['arquivos']:
            rotulo = 'stdin' if arquivo == '-' else arquivo
            try:
                dados = sys.stdin.buffer.read() if arquivo == '-' else open(arquivo, 'rb').read()
            except OSError as exc:
                raise CommandError(f'Não foi possível ler {rotulo}: {exc}') from exc
            if not dados:
                raise CommandError(f'Planilha vazia ({rotulo}).')
            # read_only lê as abas sob demanda, então o aviso pode sair depois do load.
            warnings.filterwarnings('ignore', message='Data Validation extension')
            wb = openpyxl.load_workbook(io.BytesIO(dados), data_only=True, read_only=True)

            nomes = []
            if ABA_CLIENTES in wb.sheetnames:
                nomes += [(n, f'{rotulo} / {ABA_CLIENTES}') for n in self._ler_cabecalho(wb[ABA_CLIENTES])]
            if ABA_SAIDA in wb.sheetnames:
                nomes += [(n, f'{rotulo} / {ABA_SAIDA}') for n in self._ler_saidas(wb[ABA_SAIDA])]
            if not nomes:
                raise CommandError(f'{rotulo}: nenhum cliente encontrado nas abas '
                                   f'{ABA_CLIENTES} / {ABA_SAIDA}. Abas: {wb.sheetnames}')

            for nome, onde in nomes:
                chave = nome.upper()
                if PADRAO_TESTE.search(nome) or chave in ignorar:
                    ignorados.add(nome)
                    continue
                if chave not in encontrados:
                    encontrados[chave] = nome
                    origem[chave] = onde

        existentes = {n.upper(): n for n in Client.objects.values_list('name', flat=True)}
        novos = sorted((encontrados[c] for c in encontrados if c not in existentes), key=str.upper)
        ja_existiam = sorted((existentes[c] for c in encontrados if c in existentes), key=str.upper)

        with transaction.atomic():
            Client.objects.bulk_create([Client(name=n) for n in novos])
            if opts['dry_run']:
                transaction.set_rollback(True)

        self._relatorio(novos, ja_existiam, sorted(ignorados, key=str.upper),
                        {encontrados[c]: origem[c] for c in encontrados}, opts['dry_run'])

    def _ler_cabecalho(self, ws):
        """Primeira linha (depois do título) com 2+ células preenchidas = nomes dos clientes."""
        for n, row in enumerate(ws.iter_rows(values_only=True, max_row=10), start=1):
            if n == 1:
                continue  # título "CLIENTES"
            nomes = [_nome(c) for c in row]
            nomes = [c for c in nomes if c and c.upper() != 'PRODUTO']
            if len(nomes) >= 2:
                return nomes
        return []

    def _ler_saidas(self, ws):
        linhas = ws.iter_rows(values_only=True)
        col = None
        for row in linhas:
            cab = [_nome(c).upper() for c in row]
            if 'CLIENTE' in cab:
                col = cab.index('CLIENTE')
                break
        if col is None:
            return []
        return [n for row in linhas if len(row) > col and (n := _nome(row[col]))]

    def _relatorio(self, novos, ja_existiam, ignorados, origem, dry_run):
        w = self.stdout.write
        w(f'Clientes novos: {len(novos)}')
        for n in novos:
            w(f'  + {n}  ({origem[n]})')
        w(f'Já existiam no sistema: {len(ja_existiam)}')
        for n in ja_existiam:
            w(f'  = {n}')
        if ignorados:
            w(self.style.WARNING(f'Ignorados (teste/--ignorar): {", ".join(ignorados)}'))
        if dry_run:
            w(self.style.WARNING('DRY-RUN: nada foi gravado (tudo desfeito).'))
        else:
            w(self.style.SUCCESS('Importação concluída.'))
