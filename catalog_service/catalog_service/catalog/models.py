from django.db import models
import uuid
from cloudinary_storage.storage import MediaCloudinaryStorage

class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    start_at = models.DateTimeField()
    price_cents = models.PositiveIntegerField()
    total_tickets = models.PositiveIntegerField()
    tickets_sold = models.PositiveIntegerField(default=0)
    tickets_held = models.PositiveIntegerField(default=0)
    
    image = models.ImageField(
        upload_to='events/', 
        storage=MediaCloudinaryStorage(),
        null=True, 
        blank=True
    )  # Explicitly uses Cloudinary storage
    
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
        remaining = self.total_tickets - self.tickets_sold - self.tickets_held
        return remaining if remaining > 0 else 0