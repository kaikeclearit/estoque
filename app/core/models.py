from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

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

    class Meta(AbstractUser.Meta):
        permissions = [
            ('manage_users', 'Pode criar usuários e atribuir perfis'),
        ]

    @property
    def role(self):
        """Nome do perfil (grupo) principal do usuário, ou None se não tiver."""
        from core.roles import ROLE_NAMES
        names = set(self.groups.values_list('name', flat=True))
        return next((r for r in ROLE_NAMES if r in names), None)

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

class ActiveProductManager(models.Manager):
    """Manager padrão: esconde produtos excluídos de listas, buscas e formulários."""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Product(models.Model):
    """
    Dados imutáveis do produto.
    NÃO contém quantidade, pois a quantidade depende do local.

    A exclusão é LÓGICA (is_deleted): o produto some das telas, mas o
    histórico de entradas/saídas continua apontando para ele, com a tag
    "Produto excluído".
    """
    name = models.CharField(max_length=255, verbose_name="Nome do Produto")
    model = models.CharField(max_length=255, blank=True, null=False, verbose_name="Modelo")
    manufacturer = models.CharField(max_length=255, blank=True, null=False, verbose_name="Fabricante")
    product_id = models.CharField(max_length=255, blank=True, null=True, verbose_name= "ID do Produto")
    is_deleted = models.BooleanField(default=False, verbose_name="Excluído")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Excluído em")
    deleted_by = models.ForeignKey(
        'Employee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deleted_products', verbose_name="Excluído por",
    )

    objects = ActiveProductManager()   # padrão: só produtos ativos
    all_objects = models.Manager()     # inclui os excluídos

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        constraints = [
            # ID do produto é único só entre os ativos (permite recadastrar após excluir)
            models.UniqueConstraint(
                fields=['product_id'], condition=models.Q(is_deleted=False),
                name='unique_active_product_id',
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.model or ''}"

    def soft_delete(self, user):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

# --- 3. ESTOQUE E LOCALIZAÇÃO ---
class Location(models.Model):
    """
    Localidade de estoque (MAO, SP, BSB...). Cadastrada pela tela "Localidades".
    O código é a chave primária e é o valor gravado nas tabelas de estoque.
    Localidade inativa some dos formulários e do painel, mas o histórico fica.
    """
    code = models.CharField(
        max_length=10, primary_key=True, verbose_name="Código",
        help_text="Sigla curta, em maiúsculas (ex.: MAO, SP, BSB). Não pode ser alterada depois.",
    )
    name = models.CharField(max_length=100, verbose_name="Nome")
    is_active = models.BooleanField(default=True, verbose_name="Ativa")

    class Meta:
        verbose_name = "Localidade"
        verbose_name_plural = "Localidades"
        ordering = ['code']

    def __str__(self):
        return self.code

    @property
    def label(self):
        return f"{self.code} — {self.name}"


def active_location_choices():
    """[(código, nome)] das localidades ativas, para abas e filtros."""
    return list(Location.objects.filter(is_active=True).values_list('code', 'name'))


def location_field(**kwargs):
    """FK para Location mantendo a coluna 'location' (com o código) no banco."""
    return models.ForeignKey(Location, on_delete=models.PROTECT, db_column='location',
                             verbose_name="Localidade", **kwargs)


class ProductStock(models.Model):
    """
    Tabela Pivô que guarda ONDE e QUANTO tem de cada produto.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks')
    location = location_field(related_name='stocks')
    quantity = models.IntegerField(default=0, verbose_name="Saldo Atual")
    minimum_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Estoque Mínimo",
        help_text="Abaixo ou igual a este saldo o item entra como crítico (precisa comprar).",
    )

    class Meta:
        unique_together = ('product', 'location')
        verbose_name = "Estoque por Local"
        verbose_name_plural = "Estoques"
        # ⭐ ADICIONAR CONSTRAINT PARA PREVENIR ESTOQUE NEGATIVO
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name='quantity_non_negative'
            )
        ]
        permissions = [
            ('set_stock_quantity', 'Pode ajustar o saldo diretamente (sem entrada/saída)'),
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

    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    entry_type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        default='COMPRA', 
        verbose_name="Tipo de Entrada"
    )
    nf_number = models.CharField('Nota Fiscal', max_length=50, null=False, blank=True)
    location = location_field(related_name='entries')
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

class StockOutOrder(models.Model):
    """
    Pedido de saída (carrinho): agrupa vários itens que saíram juntos,
    por exemplo para um mesmo projeto/cliente. Cada item é um StockOut.
    """
    client = models.ForeignKey(Client, on_delete=models.PROTECT, verbose_name="Destino/Cliente")
    project = models.CharField(max_length=255, blank=True, verbose_name="Projeto / Referência")
    movement_type = models.CharField(max_length=20, verbose_name="Tipo de Movimentação")
    observation = models.TextField(blank=True, verbose_name="Observação")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, verbose_name="Responsável")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pedido de Saída"
        verbose_name_plural = "Pedidos de Saída"
        ordering = ['-created_at']

    def __str__(self):
        return f"Pedido #{self.pk}"


class StockOut(models.Model):
    """Saída de materiais"""
    TYPE_CHOICES = [
        ('SAIDA', 'Saída Padrão'),
        ('EMPRESTIMO', 'Empréstimo'),
        ('DESCARTE', 'Descarte/Quebra'),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    location = location_field(related_name='outputs')
    movement_type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        default='SAIDA', 
        verbose_name="Tipo de Movimentação"
    )
    scheduled_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Data prevista de devolução",
        help_text="Opcional. Usado em empréstimos.",
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
    order = models.ForeignKey(
        StockOutOrder, on_delete=models.PROTECT, null=True, blank=True,
        related_name='items', verbose_name="Pedido",
    )
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
                        f"Estoque insuficiente de {self.product.name} em {self.location_id}! "
                        f"Disponível: {current}, Solicitado: {self.quantity}"
                    )
                
                # Baixar estoque
                stock.quantity -= self.quantity
                stock.save()
            
            # Salvar a saída
            super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Saída de Material"
        verbose_name_plural = "Saídas"


class StockAdjustment(models.Model):
    """
    Registro de ajuste DIRETO de saldo (só Admin): grava o saldo anterior,
    o novo e o motivo, para auditoria. Não gera entrada nem saída.
    """
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='adjustments')
    location = location_field(related_name='adjustments')
    old_quantity = models.IntegerField(verbose_name="Saldo anterior")
    new_quantity = models.IntegerField(verbose_name="Novo saldo")
    reason = models.CharField(max_length=255, verbose_name="Motivo")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, verbose_name="Responsável")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ajuste de Saldo"
        verbose_name_plural = "Ajustes de Saldo"
        ordering = ['-created_at']

    @property
    def difference(self):
        return self.new_quantity - self.old_quantity
