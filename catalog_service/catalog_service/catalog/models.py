from django.db import models
import uuid

class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    start_at = models.DateTimeField()
    price_cents = models.PositiveIntegerField()
    total_tickets = models.PositiveIntegerField()
    tickets_sold = models.PositiveIntegerField(default=0)
    tickets_held = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_at']
        indexes = [
            models.Index(fields=['start_at']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name

    @property
    def available_tickets(self):
        return self.total_tickets - self.tickets_sold - self.tickets_held