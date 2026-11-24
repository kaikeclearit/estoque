"""
1) Cria a tabela de Localidades e cadastra MAO, SP, BSB (e qualquer outro
   código que já exista nas tabelas de estoque, para não quebrar a FK).
2) Fim do recurso de reserva: saídas do tipo RESERVA viram SAIDA
   (o estoque delas já tinha sido baixado) com uma marcação na observação.
"""
from django.db import migrations, models

DEFAULT_LOCATIONS = {'MAO': 'Manaus', 'SP': 'São Paulo', 'BSB': 'Brasília'}


def forwards(apps, schema_editor):
    Location = apps.get_model('core', 'Location')
    codes = dict(DEFAULT_LOCATIONS)
    for model in ('ProductStock', 'StockEntry', 'StockOut'):
        M = apps.get_model('core', model)
        for code in M.objects.values_list('location', flat=True).distinct():
            if code:
                codes.setdefault(code, code)
    for code, name in codes.items():
        Location.objects.get_or_create(code=code, defaults={'name': name})

    StockOut = apps.get_model('core', 'StockOut')
    for out in StockOut.objects.filter(movement_type='RESERVA'):
        out.movement_type = 'SAIDA'
        out.observation = f"[Ex-reserva] {out.observation or ''}".strip()
        out.save(update_fields=['movement_type', 'observation'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_locations_bsb_minimum_quantity'),
    ]

    operations = [
        migrations.CreateModel(
            name='Location',
            fields=[
                ('code', models.CharField(help_text='Sigla curta, em maiúsculas (ex.: MAO, SP, BSB). Não pode ser alterada depois.', max_length=10, primary_key=True, serialize=False, verbose_name='Código')),
                ('name', models.CharField(max_length=100, verbose_name='Nome')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativa')),
            ],
            options={
                'verbose_name': 'Localidade',
                'verbose_name_plural': 'Localidades',
                'ordering': ['code'],
            },
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
