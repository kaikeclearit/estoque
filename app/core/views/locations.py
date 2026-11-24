from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import LocationForm
from core.models import Location


@login_required
@permission_required('core.change_location', raise_exception=True)
def location_list(request):
    locations = Location.objects.annotate(
        items=Count('stocks', distinct=True),
        units=Sum('stocks__quantity'),
    ).order_by('-is_active', 'code')
    return render(request, 'core/locations/list.html', {'locations': locations})


@login_required
@permission_required('core.add_location', raise_exception=True)
def location_create(request):
    form = LocationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        loc = form.save()
        messages.success(request, f'Localidade {loc.label} criada.')
        return redirect('location_list')
    return render(request, 'core/locations/form.html', {'form': form, 'title': 'Nova Localidade'})


@login_required
@permission_required('core.change_location', raise_exception=True)
def location_update(request, pk):
    loc = get_object_or_404(Location, pk=pk)
    form = LocationForm(request.POST or None, instance=loc)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Localidade {loc.label} atualizada.')
        return redirect('location_list')
    return render(request, 'core/locations/form.html', {'form': form, 'title': f'Editar {loc.label}'})
