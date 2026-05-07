from django import forms
from .models import Product, Client, StockEntry, StockOut

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

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CLEARIT - AM'}),
        }


class StockEntryForm(forms.ModelForm):
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

class StockOutForm(forms.ModelForm):
    class Meta:
        model = StockOut
        fields = ['product', 'location', 'movement_type', 'client', 'quantity', 'scheduled_date', 'observation']
        
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'movement_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_movement_type'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_scheduled_date'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        movement_type = cleaned_data.get('movement_type')
        scheduled_date = cleaned_data.get('scheduled_date')
        
        # ⭐ REMOVIDA A VALIDAÇÃO DE ESTOQUE AQUI
        # Motivo: Causa race condition. A validação acontece no model.save()
        # com select_for_update() que é seguro contra concorrência
        
        # Lógica: Validação da Reserva
        if movement_type == 'RESERVA' and not scheduled_date:
            self.add_error('scheduled_date', 'Para reservas, é obrigatório informar a data prevista.')

        return cleaned_data