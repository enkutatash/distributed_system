from rest_framework import serializers
from .models import Reservation

class ReservationCreateSerializer(serializers.ModelSerializer):
    event_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = Reservation
        fields = ['event_id', 'quantity']

class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            'id', 'user_id', 'event_id', 'quantity', 'status',
            'amount_cents', 'expires_at', 'payment_intent_id', 'created_at'
        ]
        read_only_fields = ['user_id', 'status', 'amount_cents', 'expires_at', 'payment_intent_id', 'created_at']