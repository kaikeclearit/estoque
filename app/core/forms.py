from django import forms
from .models import Product, Client, StockEntry, StockOut, ProductStock, Location


class LocationChoiceField(forms.ModelChoiceField):
    """Select de localidade mostrando 'MAO — Manaus' (só ativas)."""
    def __init__(self, **kwargs):
        kwargs.setdefault('queryset', Location.objects.filter(is_active=True))
        kwargs.setdefault('label', 'Localidade')
        kwargs.setdefault('widget', forms.Select(attrs={'class': 'form-select'}))
        super().__init__(**kwargs)

    def label_from_instance(self, obj):
        return obj.label

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'model', 'manufacturer', 'product_id']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Mouse Logitech'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'product_id': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Um campo de estoque mínimo por localidade (min_MAO, min_SP, min_BSB...)
        current = {}
        if self.instance.pk:
            current = dict(self.instance.stocks.values_list('location', 'minimum_quantity'))
        for loc in Location.objects.filter(is_active=True):
            code = loc.code
            self.fields[f'min_{code}'] = forms.IntegerField(
                label=f'Estoque mínimo — {loc.label}', min_value=0, required=False,
                initial=current.get(code, 0),
                help_text='Abaixo ou igual a isso o item aparece como crítico no painel. 0 = sem mínimo.',
                widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            )

    def save(self, commit=True):
        product = super().save(commit=commit)
        if commit:
            for code in Location.objects.filter(is_active=True).values_list('code', flat=True):
                minimum = self.cleaned_data.get(f'min_{code}') or 0
                stock = ProductStock.objects.filter(product=product, location_id=code).first()
                if stock:
                    if stock.minimum_quantity != minimum:
                        stock.minimum_quantity = minimum
                        stock.save(update_fields=['minimum_quantity'])
                elif minimum > 0:
                    # Passa a controlar o item nesta localidade (saldo 0 => "em falta")
                    ProductStock.objects.create(product=product, location_id=code,
                                                quantity=0, minimum_quantity=minimum)
        return product

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CLEARIT - AM'}),
        }


class StockEntryForm(forms.ModelForm):
    location = LocationChoiceField()

    class Meta:
        model = StockEntry
        fields = ['product', 'entry_type', 'nf_number', 'location', 'quantity'] 
        
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select', 'id': 'id_product_entry'}),
            'entry_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_entry_type'}),
            'nf_number': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_nf_number'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class CartAddForm(forms.Form):
    """Adicionar item ao carrinho de saída."""
    product = forms.ModelChoiceField(
        label='Produto', queryset=Product.objects.order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_product'}))
    location = LocationChoiceField(widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_location'}))
    quantity = forms.IntegerField(
        label='Quantidade', min_value=1, initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'id': 'id_quantity'}))


class CartCheckoutForm(forms.Form):
    """Dados comuns a todos os itens do pedido de saída."""
    client = forms.ModelChoiceField(
        label='Destino / Cliente', queryset=Client.objects.order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_client'}))
    movement_type = forms.ChoiceField(
        label='Tipo de saída', choices=StockOut.TYPE_CHOICES, initial='SAIDA',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_movement_type'}))
    project = forms.CharField(
        label='Projeto / Referência', required=False, max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Implantação rede - Bloco B'}))
    scheduled_date = forms.DateField(
        label='Data prevista de devolução', required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_scheduled_date'}))
    observation = forms.CharField(
        label='Observação', required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('movement_type') != 'EMPRESTIMO':
            cleaned['scheduled_date'] = None
        return cleaned


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['code', 'name', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'Ex: REC', 'maxlength': 10}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Recife'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # O código é a chave gravada no histórico: não muda depois de criado
            self.fields['code'].disabled = True

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code.isalnum():
            raise forms.ValidationError('Use só letras e números (ex.: MAO, SP, BSB).')
        return code


class StockAdjustmentForm(forms.Form):
    """Ajuste direto de saldo (só Admin): um campo de novo saldo por localidade ativa."""
    reason = forms.CharField(
        label='Motivo do ajuste', max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Inventário físico de 24/11'}),
    )

    def __init__(self, *args, product, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        current = dict(product.stocks.values_list('location_id', 'quantity'))
        self.locations = list(Location.objects.filter(is_active=True))
        for loc in self.locations:
            self.fields[f'qty_{loc.code}'] = forms.IntegerField(
                label=loc.label, min_value=0, initial=current.get(loc.code, 0),
                widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            )
            self.fields[f'qty_{loc.code}'].current = current.get(loc.code, 0)

    def changes(self):
        """[(location, saldo_atual, novo_saldo)] só das localidades alteradas."""
        out = []
        for loc in self.locations:
            field = self.fields[f'qty_{loc.code}']
            new = self.cleaned_data[f'qty_{loc.code}']
            if new != field.current:
                out.append((loc, field.current, new))
        return out

    def clean(self):
        cleaned = super().clean()
        if not self.errors and not self.changes():
            raise forms.ValidationError('Nenhum saldo foi alterado.')
        return cleaned

# --- USUÁRIOS E PERFIS ---
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group
from core.roles import ROLE_NAMES, ROLE_DESCRIPTIONS

ROLE_CHOICES = [(r, f'{r} — {ROLE_DESCRIPTIONS[r]}') for r in ROLE_NAMES]


class _UserRoleForm(forms.ModelForm):
    """Base: dados do usuário + perfil. Nunca mexe em is_superuser/is_staff."""
    role = forms.ChoiceField(label='Perfil', choices=ROLE_CHOICES,
                             widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {'username': 'Usuário (login)', 'first_name': 'Nome',
                  'last_name': 'Sobrenome', 'email': 'E-mail'}
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def _clean_password_pair(self, required):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if not p1 and not p2 and not required:
            return None
        if p1 != p2:
            self.add_error('password2', 'As senhas não conferem.')
            return None
        try:
            password_validation.validate_password(p1, self.instance)
        except forms.ValidationError as e:
            self.add_error('password1', e)
            return None
        return p1

    def save_role(self, user):
        role_groups = Group.objects.filter(name__in=ROLE_NAMES)
        user.groups.remove(*role_groups)
        user.groups.add(Group.objects.get(name=self.cleaned_data['role']))


class UserCreateForm(_UserRoleForm):
    password1 = forms.CharField(label='Senha', strip=False,
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Confirmar senha', strip=False,
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))

    def clean(self):
        cleaned = super().clean()
        self._password = self._clean_password_pair(required=True)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self._password)
        user.login_type = 'LOCAL'
        user.save()
        self.save_role(user)
        return user


class UserUpdateForm(_UserRoleForm):
    is_active = forms.BooleanField(label='Usuário ativo', required=False,
                                   widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    password1 = forms.CharField(label='Nova senha (deixe em branco para manter)', required=False, strip=False,
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Confirmar nova senha', required=False, strip=False,
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))

    def __init__(self, *args, editing_self=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].initial = self.instance.is_active
        if self.instance.role:
            self.fields['role'].initial = self.instance.role
        else:
            self.fields['role'].choices = [('', '— Sem perfil (somente leitura) —')] + ROLE_CHOICES
            self.fields['role'].required = False
        self.editing_self = editing_self
        if editing_self:
            # Evita que a pessoa se tranque fora do sistema
            for name in ('role', 'is_active'):
                self.fields[name].disabled = True
                self.fields[name].help_text = 'Você não pode alterar o próprio perfil ou se desativar.'

    def clean(self):
        cleaned = super().clean()
        self._password = self._clean_password_pair(required=False)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if not self.editing_self:
            user.is_active = self.cleaned_data['is_active']
        if self._password:
            user.set_password(self._password)
        user.save()
        if not self.editing_self and self.cleaned_data.get('role'):
            self.save_role(user)
        return user
