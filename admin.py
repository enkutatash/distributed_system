from django.contrib import admin
from .models import User, AuthToken


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	list_display = (
		'id', 'username', 'first_name', 'last_name',
		'is_staff', 'is_superuser', 'is_active', 'created_at'
	)
	search_fields = ('username', 'first_name', 'last_name')
	list_filter = ('is_staff', 'is_superuser', 'is_active')
	ordering = ('-created_at',)


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
	list_display = ('token', 'user', 'name', 'created_at', 'last_used_at')
	search_fields = ('token', 'user__username', 'name')
	raw_id_fields = ('user',)
