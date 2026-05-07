from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.models import Client
from core.forms import ClientForm
from django.db.models import Q # <--- Importante para a busca
from core.models import StockOut # Importe o modelo de Saída

# 1. READ (Listar)
def client_list(request):
    # Ordena alfabeticamente
    clients = Client.objects.all().order_by('name')
    context = {'clients': clients}
    return render(request, 'core/clients/list.html', context)

# 2. CREATE (Criar)
def client_create(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('client_list')
    else:
        form = ClientForm()
    
    return render(request, 'core/clients/form.html', {'form': form, 'title': 'Novo Cliente/Setor'})

# 3. UPDATE (Editar)
def client_update(request, pk):
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            return redirect('client_list')
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'core/clients/form.html', {'form': form, 'title': f'Editar {client.name}'})



# 1. Atualize sua view de Lista para ter Busca
@login_required
def client_list(request):
    search_query = request.GET.get('search', '') # Pega o que foi digitado
    
    clients = Client.objects.all().order_by('name')
    
    if search_query:
        # Filtra por nome (icontains ignora maiúscula/minúscula)
        clients = clients.filter(name__icontains=search_query)

    context = {
        'clients': clients,
        'search_query': search_query # Devolve para manter escrito na caixinha
    }
    return render(request, 'core/clients/list.html', context)

# 2. Crie essa NOVA view para o Modal (Igual fizemos com produto)
@login_required
def client_history_modal(request, pk):
    client = get_object_or_404(Client, pk=pk)
    
    # Busca todas as saídas para este cliente
    # select_related deixa a consulta mais rápida pegando nome do produto e do usuário
    history = StockOut.objects.filter(client=client).select_related('product', 'employee').order_by('-created_at')
    
    context = {
        'client': client,
        'history': history
    }
    return render(request, 'core/clients/_history_modal_content.html', context)