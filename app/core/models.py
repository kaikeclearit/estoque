from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver
from allauth.account.signals import user_logged_in
from django.contrib.auth.models import Group

# mail configs
import uuid
from django.utils import timezone
from datetime import timedelta

# --- 1. CONFIGURAÇÃO DE USUÁRIO HÍBRIDO ---
class Employee(AbstractUser):
    """
    Extensão do usuário padrão do Django para suportar Login Híbrido.
    Campos como username, password (hash) e email já existem no AbstractUser.
    """
    LOGIN_CHOICES = [
        ('LOCAL', 'Senha Local'),
        ('MS', 'Microsoft SSO'),
        ('HYBRID', 'Híbrido'),
    ]
    
    microsoft_oid = models.CharField(
        max_length=255, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name="Microsoft Object ID"
    )
    login_type = models.CharField(
        max_length=10, 
        choices=LOGIN_CHOICES, 
        default='LOCAL'
    )
    department = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_login_type_display()})"

# --- 2. CADASTROS BÁSICOS ---
class Client(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Nome do Cliente/Setor")
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.name

class Product(models.Model):
    """
    Dados imutáveis do produto.
    NÃO contém quantidade, pois a quantidade depende do local.
    """
    name = models.CharField(max_length=255, verbose_name="Nome do Produto")
    model = models.CharField(max_length=255, blank=True, null=False, verbose_name="Modelo")
    manufacturer = models.CharField(max_length=255, blank=True, null=False, verbose_name="Fabricante")
    product_id = models.CharField(max_length=255, blank=True, null=True, verbose_name= "ID do Produto", unique=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return f"{self.name} - {self.model or ''}"

# --- 3. ESTOQUE E LOCALIZAÇÃO ---
class ProductStock(models.Model):
    """
    Tabela Pivô que guarda ONDE e QUANTO tem de cada produto.
    """
    LOCATION_CHOICES = [
        ('MAO', 'Manaus'),
        ('SP', 'São Paulo'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks')
    location = models.CharField(max_length=3, choices=LOCATION_CHOICES)
    quantity = models.IntegerField(default=0, verbose_name="Saldo Atual")

    class Meta:
        unique_together = ('product', 'location')
        verbose_name = "Estoque por Local"
        verbose_name_plural = "Estoques"
        # ⭐ ADICIONAR CONSTRAINT PARA PREVENIR ESTOQUE NEGATIVO
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='quantity_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.product.name} ({self.location}): {self.quantity}"

# --- 4. MOVIMENTAÇÕES (AUDITORIA) ---
class StockEntry(models.Model):
    TYPE_CHOICES = [
        ('COMPRA', 'Compra (Fornecedor)'),
        ('RETORNO', 'Retorno de Empréstimo'),
        ('AJUSTE', 'Ajuste de Inventário'),
        ('DOACAO', 'Doação/Brinde'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    entry_type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        default='COMPRA', 
        verbose_name="Tipo de Entrada"
    )
    nf_number = models.CharField('Nota Fiscal', max_length=50, null=False, blank=True)
    location = models.CharField(max_length=3, choices=[('SP', 'São Paulo'), ('MAO', 'Manaus')])
    quantity = models.PositiveIntegerField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="Responsável", null=False, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # ⭐ PROTEÇÃO: Usar transação atômica
        with transaction.atomic():
            super().save(*args, **kwargs)
            
            # Usar select_for_update para travar o registro
            stock, created = ProductStock.objects.select_for_update().get_or_create(
                product=self.product, 
                location=self.location,
                defaults={'quantity': 0}
            )
            stock.quantity += self.quantity
            stock.save()

    class Meta:
        verbose_name = "Entrada de Material"
        verbose_name_plural = "Entradas"

class StockOut(models.Model):
    """Saída de materiais"""
    TYPE_CHOICES = [
        ('SAIDA', 'Saída Padrão'),
        ('RESERVA', 'Reserva Técnica'),
        ('EMPRESTIMO', 'Empréstimo'),
        ('DESCARTE', 'Descarte/Quebra'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    location = models.CharField(
        max_length=3, 
        choices=[('SP', 'São Paulo'), ('MAO', 'Manaus')]
    )
    movement_type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        default='SAIDA', 
        verbose_name="Tipo de Movimentação"
    )
    scheduled_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Data Prevista"
    )
    is_cancelled = models.BooleanField(
        default=False,
        verbose_name="Cancelada"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Cancelada em"
    )
    cancelled_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_stockouts',
        verbose_name="Cancelada por"
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    observation = models.TextField(null=True, blank=True, verbose_name="Observação")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # ⭐ PROTEÇÃO TOTAL CONTRA RACE CONDITION
        with transaction.atomic():
            if not self.pk:  # Só valida na criação
                # ⭐ select_for_update() TRAVA o registro até a transação terminar
                stock = ProductStock.objects.select_for_update().filter(
                    product=self.product, 
                    location=self.location
                ).first()
                
                current = stock.quantity if stock else 0
                
                # Validação de estoque disponível
                if not stock or stock.quantity < self.quantity:
                    raise ValueError(
                        f"Estoque insuficiente! Disponível: {current}, "
                        f"Solicitado: {self.quantity}"
                    )
                
                # Baixar estoque
                stock.quantity -= self.quantity
                stock.save()
            
            # Salvar a saída
            super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Saída de Material"
        verbose_name_plural = "Saídas"

@receiver(user_logged_in)
def atualizar_permissoes_microsoft(request, user, **kwargs):
    """
    Toda vez que o usuário logar, verificamos o cargo dele na Microsoft
    e atualizamos os grupos.
    """
    social_account = user.socialaccount_set.filter(provider='microsoft').first()
    
    if not social_account:
        print(f"⚠️ Usuário {user.username} logou, mas não tem conta Microsoft vinculada.")
        return

    data = social_account.extra_data
    job_title = data.get('jobTitle', '').lower()
    
    print(f"🔍 VERIFICANDO PERMISSÃO: {user.username} | Cargo: {job_title}")

    setores_gestores = [
        'infraestrutura',
        'pós-vendas', 'pos-vendas', 'pos vendas', 'pós vendas',
        'pós-venda', 'pos-venda', 'pos venda', 'pós venda',
        'projetos',
        'suporte',
        'qualidade'
    ]

    eh_gestor = any(setor in job_title for setor in setores_gestores)
    print(eh_gestor)
    
    grupo_gestores, _ = Group.objects.get_or_create(name='Gestores')

    if eh_gestor:
        if grupo_gestores not in user.groups.all():
            user.groups.add(grupo_gestores)
            print("GRUPO ADICIONADO: Usuário virou Gestor.")
    else:
        if grupo_gestores in user.groups.all():
            user.groups.remove(grupo_gestores)
            print("GRUPO REMOVIDO: Usuário não é mais Gestor.")


class ReservationToken(models.Model):
    """Token único para confirmação de reserva por email"""
    stock_out = models.OneToOneField(
        'StockOut', 
        on_delete=models.CASCADE,
        related_name='confirmation_token'
    )
    token = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    action = models.CharField(
        max_length=20,
        choices=[
            ('CONFIRMED', 'Retirada Confirmada'),
            ('CANCELLED', 'Não Utilizado'),
        ],
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    class Meta:
        verbose_name = "Token de Confirmação"
        verbose_name_plural = "Tokens de Confirmação"