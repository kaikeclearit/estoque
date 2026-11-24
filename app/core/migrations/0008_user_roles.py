"""
Cria os perfis de acesso (grupos) e a permissão de gerenciar usuários.

O antigo grupo "Gestores" (usado no login Microsoft) é renomeado para "Gestor",
mantendo os usuários que já estavam nele.
"""
from django.db import migrations

WRITE_PERMS = [
    'add_product', 'change_product', 'delete_product',
    'add_client', 'change_client',
    'add_stockentry',
    'add_stockout', 'change_stockout',
]
MANAGE_PERMS = ['manage_users']

ROLES = {
    'Admin': WRITE_PERMS + MANAGE_PERMS,
    'Dev': WRITE_PERMS + MANAGE_PERMS,
    'Gestor': WRITE_PERMS + MANAGE_PERMS,
    'Pós-vendas': WRITE_PERMS,
    'Pré-vendas': [],
}


def create_roles(apps, schema_editor):
    # Em banco novo as permissões só são criadas no post_migrate;
    # forçamos a criação aqui para poder associá-las aos grupos.
    from django.contrib.auth.management import create_permissions
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    old = Group.objects.filter(name='Gestores').first()
    if old and not Group.objects.filter(name='Gestor').exists():
        old.name = 'Gestor'
        old.save()

    for name, codenames in ROLES.items():
        group, _ = Group.objects.get_or_create(name=name)
        perms = Permission.objects.filter(content_type__app_label='core', codename__in=codenames)
        missing = set(codenames) - set(perms.values_list('codename', flat=True))
        if missing:
            raise RuntimeError(f'Permissões não encontradas para {name}: {missing}')
        group.permissions.set(perms)


def remove_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=[n for n in ROLES if n != 'Gestor']).delete()
    Group.objects.filter(name='Gestor').update(name='Gestores')


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('core', '0007_productstock_quantity_non_negative'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='employee',
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'permissions': [('manage_users', 'Pode criar usuários e atribuir perfis')],
            },
        ),
        migrations.RunPython(create_roles, remove_roles),
    ]
