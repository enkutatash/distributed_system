from django.contrib import admin
from .models import Event

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_at', 'price_cents', 'total_tickets', 'available_tickets']
    list_filter = ['start_at']
    search_fields = ['name']
    readonly_fields = ['tickets_sold', 'tickets_held', 'created_at']