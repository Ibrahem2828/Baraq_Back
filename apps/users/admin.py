from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    ordering = ('-created_at',)
    list_display = (
        'email',
        'full_name',
        'role',
        'phone_number',
        'is_active',
        'is_staff',
        'created_at',
    )
    list_filter = (
        'role',
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at',
    )
    search_fields = ('email', 'full_name', 'phone_number')
    readonly_fields = ('created_at', 'updated_at', 'last_login')
    filter_horizontal = ('groups', 'user_permissions')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('full_name', 'phone_number', 'role')}),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Important Dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'full_name',
                    'phone_number',
                    'role',
                    'password1',
                    'password2',
                    'is_active',
                ),
            },
        ),
    )
