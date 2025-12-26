# booking/views.py (FULL UPDATED FILE)

from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from .models import Reservation
from .serializers import ReservationCreateSerializer, ReservationSerializer

# gRPC imports (now for both Catalog and Inventory)
import grpc
import ticketing_pb2
import ticketing_pb2_grpc

def get_event_via_grpc(event_id: str):
    """Get event details from Catalog (still needed for price)"""
    try:
        with grpc.insecure_channel('localhost:60001') as channel:
            stub = ticketing_pb2_grpc.CatalogServiceStub(channel)
            request = ticketing_pb2.GetEventRequest(event_id=event_id)
            response = stub.GetEvent(request, timeout=5.0)
            if not response.id:
                return None
            return {
                'price_cents': response.price_cents,
            }
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return None
        raise

def hold_tickets_via_inventory(event_id: str, reservation_id: str, quantity: int):
    """Atomic hold via Inventory Service"""
    try:
        with grpc.insecure_channel('localhost:50052') as channel:  # Inventory gRPC port
            stub = ticketing_pb2_grpc.InventoryServiceStub(channel)
            request = ticketing_pb2.HoldTicketsRequest(
                event_id=event_id,
                quantity=quantity,
                reservation_id=reservation_id,
                ttl_seconds=600  # 10 minutes
            )
            response = stub.HoldTickets(request, timeout=5.0)
            return response.success
    except grpc.RpcError as e:
        print(f"Inventory gRPC error: {e.code()} - {e.details()}")
        return False

class ReservationViewSet(viewsets.GenericViewSet,
                         mixins.CreateModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.ListModelMixin):
    queryset = Reservation.objects.all()
    permission_classes = [IsAuthenticated]  # Your custom permission

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservationCreateSerializer
        return ReservationSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event_id = serializer.validated_data['event_id']
        quantity = serializer.validated_data['quantity']
        user_id = request.headers.get('X-User-ID') or request.user_id  # From Gateway

        if not user_id:
            return Response({"error": "User ID required"}, status=401)

        # 1. Get price from Catalog (still needed)
        event_data = get_event_via_grpc(str(event_id))
        if event_data is None:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

        price_cents = event_data['price_cents']

        # 2. Atomic hold via Inventory (NEW!)
        reservation = Reservation(
            user_id=user_id,
            event_id=event_id,
            quantity=quantity,
            amount_cents=price_cents * quantity,
            status='AWAITING_PAYMENT',
        )
        reservation.save()  # Save first to get ID

        hold_success = hold_tickets_via_inventory(str(event_id), str(reservation.id), quantity)
        if not hold_success:
            reservation.delete()  # Rollback if hold fails
            return Response(
                {"error": "Not enough tickets available"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, pk=None):
        reservation = self.get_object()
        is_staff = request.headers.get('X-Is-Staff', 'false').lower() == 'true'

        if not is_staff:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

        return Response(ReservationSerializer(reservation).data)

    def list(self, request):
        is_staff = request.headers.get('X-Is-Staff', 'false').lower() == 'true'
        if not is_staff:
            return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

        qs = self.get_queryset().order_by('-created_at')

        event_id = request.query_params.get('event_id')
        if event_id:
            try:
                # Ensure valid UUID string; DB field is UUIDField
                import uuid
                evt = uuid.UUID(str(event_id))
                qs = qs.filter(event_id=evt)
            except ValueError:
                return Response({"error": "Invalid event_id"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ReservationSerializer(qs, many=True)
        return Response(serializer.data)

    def cancel(self, request, pk=None):
        reservation = self.get_object()
        user_id = request.headers.get('X-User-ID') or request.user_id
        if str(reservation.user_id) != user_id:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        if reservation.status not in ['AWAITING_PAYMENT', 'EXPIRED']:
            return Response({"error": "Cannot cancel reservation in current status"}, status=status.HTTP_400_BAD_REQUEST)

        # NEW: Release tickets via Inventory
        release_success = release_tickets_via_inventory(str(reservation.event_id), str(reservation.id), reservation.quantity)
        if release_success:
            reservation.status = 'CANCELLED'
            reservation.save()
            return Response({"status": "cancelled"})

        return Response({"error": "Failed to release tickets"}, status=500)

def release_tickets_via_inventory(event_id: str, reservation_id: str, quantity: int):
    """Release held tickets"""
    try:
        with grpc.insecure_channel('localhost:50052') as channel:
            stub = ticketing_pb2_grpc.InventoryServiceStub(channel)
            request = ticketing_pb2.ReleaseTicketsRequest(
                event_id=event_id,
                quantity=quantity,
                reservation_id=reservation_id
            )
            response = stub.ReleaseTickets(request, timeout=5.0)
            return response.success
    except grpc.RpcError:
        return False