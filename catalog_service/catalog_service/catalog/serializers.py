from rest_framework import serializers
from .models import Event

class EventSerializer(serializers.ModelSerializer):
    available_tickets = serializers.IntegerField(read_only=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'name',
            'start_at',
            'price_cents',
            'total_tickets',
            'tickets_sold',
            'tickets_held',
            'available_tickets',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['tickets_sold', 'tickets_held', 'created_at', 'available_tickets']