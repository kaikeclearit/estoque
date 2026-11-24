from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import UserCreateForm, UserUpdateForm
from core.pagination import paginate
from core.roles import ROLE_DESCRIPTIONS

Employee = get_user_model()
manage_users_required = permission_required('core.manage_users', raise_exception=True)


@login_required
@manage_users_required
def user_list(request):
    search = request.GET.get('search', '').strip()
    users = Employee.objects.prefetch_related('groups').order_by('-is_active', 'username')
    if search:
        users = users.filter(Q(username__icontains=search) | Q(first_name__icontains=search)
                             | Q(last_name__icontains=search) | Q(email__icontains=search))
    page_obj = paginate(request, users)
    return render(request, 'core/users/list.html', {
        'users': page_obj, 'page_obj': page_obj, 'search_query': search, 'role_descriptions': ROLE_DESCRIPTIONS,
    })


@login_required
@manage_users_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'Usuário "{user.username}" criado com perfil {user.role}.')
        return redirect('user_list')
    return render(request, 'core/users/form.html', {'form': form, 'title': 'Novo Usuário'})


@login_required
@manage_users_required
def user_update(request, pk):
    user = get_object_or_404(Employee, pk=pk)
    # Só um superusuário pode editar outro superusuário
    if user.is_superuser and not request.user.is_superuser:
        raise PermissionDenied
    editing_self = user.pk == request.user.pk
    form = UserUpdateForm(request.POST or None, instance=user, editing_self=editing_self)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if editing_self and form._password:
            update_session_auth_hash(request, user)  # não desloga ao trocar a própria senha
        messages.success(request, f'Usuário "{user.username}" atualizado.')
        return redirect('user_list')
    return render(request, 'core/users/form.html', {
        'form': form, 'title': f'Editar {user.username}', 'edited_user': user,
    })
