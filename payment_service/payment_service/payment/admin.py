from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ('id', 'reservation_id', 'status', 'amount_cents', 'stripe_payment_intent', 'created_at')
	search_fields = ('id', 'reservation_id', 'stripe_payment_intent')
