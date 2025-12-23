from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'total_tickets',
		'tickets_held',
		'tickets_sold',
		'available_tickets_display',
	)
	search_fields = ('id',)
	list_per_page = 25
	ordering = ('id',)
	readonly_fields = ('available_tickets_display',)

	def available_tickets_display(self, obj):
		return obj.available_tickets
	available_tickets_display.short_description = 'Available Tickets'
