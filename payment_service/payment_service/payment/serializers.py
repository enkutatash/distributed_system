from rest_framework import serializers
from .models import Payment


class PaymentCreateSerializer(serializers.Serializer):
    reservation_id = serializers.UUIDField()


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id',
            'reservation_id',
            'stripe_payment_intent',
            'status',
            'amount_cents',
            'provider_payload',
            'created_at',
        ]
        read_only_fields = fields
