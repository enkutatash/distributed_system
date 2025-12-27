from django.db import models
import uuid


class Payment(models.Model):
	STATUS_CHOICES = (
		('PENDING', 'Pending'),
		('SUCCEEDED', 'Succeeded'),
		('FAILED', 'Failed'),
	)

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	reservation_id = models.UUIDField()
	stripe_payment_intent = models.CharField(max_length=255, blank=True, null=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
	amount_cents = models.PositiveIntegerField()
	provider_payload = models.JSONField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Payment {self.id} - {self.status}"
