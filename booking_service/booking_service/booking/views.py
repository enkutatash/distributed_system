# booking/views.py

from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import Reservation
from .serializers import ReservationCreateSerializer, ReservationSerializer

# gRPC imports
import grpc
import ticketing_pb2
import ticketing_pb2_grpc


def get_event_via_grpc(event_id: str):
    """
    Calls Catalog Service via gRPC to fetch event details.
    Returns a dict with 'price_cents' and 'available_tickets' on success,
    or None if the event is not found.
    """
    try:
        with grpc.insecure_channel('localhost:50051') as channel:  # Catalog gRPC port
            stub = ticketing_pb2_grpc.CatalogServiceStub(channel)
            request = ticketing_pb2.GetEventRequest(event_id=event_id)
            response = stub.GetEvent(request, timeout=5.0)

            # If event not found, response.id will be empty string
            if not response.id:
                return None

            return {
                'price_cents': response.price_cents,
                'available_tickets': response.available_tickets,
            }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return None
        # Log other errors (unreachable service, etc.) – in production use logger
        print(f"gRPC error when contacting Catalog: {e.code()} - {e.details()}")
        raise  # Will result in 500 error; you can customize handling


class ReservationViewSet(viewsets.GenericViewSet,
                         mixins.CreateModelMixin,
                         mixins.RetrieveModelMixin):
    queryset = Reservation.objects.all()
    permission_classes = [IsAuthenticated]

    # Require authentication for all actions

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservationCreateSerializer
        return ReservationSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_id = serializer.validated_data['event_id']
        quantity = serializer.validated_data['quantity']

        # Fetch event details via gRPC
        event_data = get_event_via_grpc(str(event_id))
        if event_data is None:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

        available = event_data['available_tickets']
        price_cents = event_data['price_cents']

        if available < quantity:
            return Response(
                {"error": "Not enough tickets available"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the reservation (temporary hold – real hold comes with Inventory Service)
        reservation = Reservation(
            user_id=request.user_id,  # Set by your authentication middleware/class
            event_id=event_id,
            quantity=quantity,
            amount_cents=price_cents * quantity,
            status='AWAITING_PAYMENT',
        )
        reservation.save()

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED
        )

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
            return Response(
                {"error": "Cannot cancel reservation in current status"},
                status=status.HTTP_400_BAD_REQUEST
            )

        reservation.status = 'CANCELLED'
        reservation.save()

        # TODO: Later call Inventory Service to release tickets via gRPC
        return Response({"status": "cancelled"})