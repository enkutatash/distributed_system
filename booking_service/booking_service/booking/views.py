from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import Reservation
from .serializers import ReservationCreateSerializer, ReservationSerializer
import requests

CATALOG_BASE_URL = "http://localhost:8001/api/v1"  # Change if Catalog runs elsewhere

class ReservationViewSet(viewsets.GenericViewSet,
                         mixins.CreateModelMixin,
                         mixins.RetrieveModelMixin):
    queryset = Reservation.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservationCreateSerializer
        return ReservationSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_id = serializer.validated_data['event_id']
        quantity = serializer.validated_data['quantity']

        # Call Catalog Service to validate event and get details
        try:
            event_response = requests.get(f"{CATALOG_BASE_URL}/events/{event_id}/")
            if event_response.status_code != 200:
                return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
            event = event_response.json()
        except requests.RequestException:
            return Response({"error": "Cannot reach Catalog Service"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        available = event['available_tickets']
        price_cents = event['price_cents']

        if available < quantity:
            return Response({"error": "Not enough tickets available"}, status=status.HTTP_400_BAD_REQUEST)

        # Temporary hold: just proceed (real hold will come with Inventory Service)
        reservation = Reservation(
            user_id=request.user_id,  # Attached by auth middleware or custom auth
            event_id=event_id,
            quantity=quantity,
            amount_cents=price_cents * quantity,
            status='AWAITING_PAYMENT',
        )
        reservation.save()

        return Response(ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        reservation = self.get_object()
        if str(reservation.user_id) != request.user_id:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        return Response(ReservationSerializer(reservation).data)

    def cancel(self, request, pk=None):
        reservation = self.get_object()
        if str(reservation.user_id) != request.user_id:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        if reservation.status not in ['AWAITING_PAYMENT', 'EXPIRED']:
            return Response({"error": "Cannot cancel reservation in current status"}, status=status.HTTP_400_BAD_REQUEST)

        reservation.status = 'CANCELLED'
        reservation.save()

        # Later: call Inventory.release here
        return Response({"status": "cancelled"})