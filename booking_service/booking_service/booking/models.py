from django.db import models
import uuid
from django.utils import timezone

class Reservation(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('AWAITING_PAYMENT', 'Awaiting Payment'),
        ('PAID', 'Paid'),
        ('CONFIRMED', 'Confirmed'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()  # From authenticated token (not ForeignKey since separate service)
    event_id = models.UUIDField()
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AWAITING_PAYMENT')
    amount_cents = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    payment_intent_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reservation {self.id} - {self.quantity} tickets for event {self.event_id}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)