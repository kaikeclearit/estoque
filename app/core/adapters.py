# core/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import Group

class MyAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True

# Isso força o preenchimento automático
class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        data = sociallogin.account.extra_data
        
        # Pega o cargo e converte para minúsculo (ex: "Analista de Suporte" -> "analista de suporte")
        job_title = data.get('jobTitle', '').lower()
        print(job_title)
        # --- DEFINIÇÃO DAS PALAVRAS-CHAVE PERMITIDAS ---
        # Se o cargo tiver QUALQUER UMA dessas, ganha acesso de edição.
        setores_permitidos = [
            'infraestrutura',
            'pós-vendas', 'pos-vendas', 'pos vendas', # Variações de escrita
            'projetos',
            'suporte',
            'qualidade'
        ]

        # Verifica se o cargo contem algum dos setores permitidos
        tem_permissao = any(setor in job_title for setor in setores_permitidos)

        if tem_permissao:
            # Cria ou pega o grupo "Gestores"
            grupo_gestores, _ = Group.objects.get_or_create(name='Gestores')
            user.groups.add(grupo_gestores)
            print(f"✅ ACESSO LIBERADO: {user.username} ({job_title}) entrou em Gestores.")
        else:
            # Se quiser ser rigoroso, remove do grupo caso tenha mudado de cargo
            grupo_gestores = Group.objects.filter(name='Gestores').first()
            if grupo_gestores and grupo_gestores in user.groups.all():
                user.groups.remove(grupo_gestores)
            print(f"🔒 ACESSO LEITURA: {user.username} ({job_title}) - Apenas visualização.")

        user.save()
        return user