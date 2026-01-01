from rest_framework import serializers
from .models import Event


class EventProvisionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField()
    total_tickets = serializers.IntegerField(min_value=0)

    class Meta:
        model = Event
        fields = ["id", "total_tickets"]
