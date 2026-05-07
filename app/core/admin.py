from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Employee, Client, Product, ProductStock, StockEntry, StockOut

# Configura o Admin do Usuário personalizado
admin.site.register(Employee, UserAdmin)

# Configura os Cadastros
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'model', 'manufacturer')
    search_fields = ('name', 'model')

@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'location', 'quantity')
    list_filter = ('location',)

@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'product', 'quantity', 'location', 'employee')
    list_filter = ('location', 'entry_type')

@admin.register(StockOut)
class StockOutAdmin(admin.ModelAdmin):
    list_display = ('product', 'location', 'movement_type', 'quantity', 'client', 'employee', 'created_at')
    list_filter = ('location', 'movement_type', 'created_at') 
    search_fields = ('product__name', 'client__name')

admin.site.register(Client)