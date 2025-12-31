from django.contrib import admin
from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
	list_display = ('id', 'user_id', 'event_id', 'quantity', 'status', 'amount_cents', 'created_at')
	search_fields = ('id', 'user_id', 'event_id')
	list_filter = ('status', 'created_at')
