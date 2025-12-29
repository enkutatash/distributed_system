from django.db import models
import uuid

class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    total_tickets = models.PositiveIntegerField()
    tickets_sold = models.PositiveIntegerField(default=0)
    tickets_held = models.PositiveIntegerField(default=0)

    @property
    def available_tickets(self):
        return self.total_tickets - self.tickets_sold - self.tickets_held