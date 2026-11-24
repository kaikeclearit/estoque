"""
Novas regras de perfil:
- Saídas (retirada) e reversão de saídas (correção): só Admin e Gestor.
- Cadastro de localidades: Admin e Gestor.
- Ajuste direto de saldo: só Admin.
"""
from django.db import migrations

BASE_WRITE = [
    'add_product', 'change_product', 'delete_product',
    'add_client', 'change_client',
    'add_stockentry',
]
STOCKOUT = ['add_stockout', 'change_stockout']
LOCATIONS = ['add_location', 'change_location']
MANAGE_USERS = ['manage_users']
ADJUST = ['set_stock_quantity']

ROLES = {
    'Admin': BASE_WRITE + STOCKOUT + LOCATIONS + MANAGE_USERS + ADJUST,
    'Gestor': BASE_WRITE + STOCKOUT + LOCATIONS + MANAGE_USERS,
    'Dev': BASE_WRITE + MANAGE_USERS,
    'Pós-vendas': BASE_WRITE,
    'Pré-vendas': [],
}


def apply_roles(apps, schema_editor):
    from django.contrib.auth.management import create_permissions
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    for name, codenames in ROLES.items():
        group, _ = Group.objects.get_or_create(name=name)
        perms = Permission.objects.filter(content_type__app_label='core', codename__in=codenames)
        missing = set(codenames) - set(perms.values_list('codename', flat=True))
        if missing:
            raise RuntimeError(f'Permissões não encontradas para {name}: {missing}')
        group.permissions.set(perms)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_stock_location_fk_soft_delete_adjustments'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(apply_roles, migrations.RunPython.noop),
    ]
