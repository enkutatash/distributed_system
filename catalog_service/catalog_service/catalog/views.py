from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Event
import httpx
from .serializers import EventSerializer
from .filters import EventFilter
import logging
import os
import redis

logger = logging.getLogger(__name__)


def get_inventory_counts(event_id, fallback):
    """Pull latest held/sold/available from Inventory's Redis; fall back to provided values."""
    try:
        redis_host = os.environ.get('REDIS_HOST', 'redis')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        client = redis.Redis(host=redis_host, port=redis_port, db=0)
        held_key = f"event:{event_id}:held"
        sold_key = f"event:{event_id}:sold"
        available_key = f"event:{event_id}:available"
        r_held, r_sold, r_available = client.mget([held_key, sold_key, available_key])

        tickets_held = int(r_held) if r_held is not None else fallback['tickets_held']
        tickets_sold = int(r_sold) if r_sold is not None else fallback['tickets_sold']
        available = int(r_available) if r_available is not None else max(fallback['total_tickets'] - tickets_sold - tickets_held, 0)
        return {
            'tickets_held': tickets_held,
            'tickets_sold': tickets_sold,
            'available_tickets': available,
        }
    except Exception:
        return {
            'tickets_held': fallback['tickets_held'],
            'tickets_sold': fallback['tickets_sold'],
            'available_tickets': max(fallback['total_tickets'] - fallback['tickets_sold'] - fallback['tickets_held'], 0),
        }

class EventViewSet(mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.CreateModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.GenericViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    def get_permissions(self):
        """
        - List and Retrieve: public (anyone)
        - Create: only admin (is_staff)
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:  
            permission_classes = [IsAuthenticated, IsAdminUser]
        return [permission() for permission in permission_classes]
    
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_class = EventFilter
    search_fields = ['name']
    ordering_fields = ['start_at', 'price_cents']
    ordering = ['start_at']  # default ordering

    def initial(self, request, *args, **kwargs):
        # Debug: log incoming requests for troubleshooting proxied calls
        try:
            key_headers = {k: v for k, v in request.headers.items() if k.lower() in ('authorization', 'content-type')}
        except Exception:
            key_headers = {}
        logger.debug("Catalog incoming request: method=%s path=%s headers=%s data=%s", request.method, request.get_full_path(), key_headers, getattr(request, 'data', None))
        return super().initial(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()

        # Provision mirrored event in Inventory immediately (synchronous)
        payload = {
            "id": str(event.id),
            "total_tickets": event.total_tickets,
        }
        try:
            inventory_base = os.environ.get("INVENTORY_HTTP_BASE", "http://inventory:8003")
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(f"{inventory_base}/api/v1/events", json=payload)
            if resp.status_code not in (200, 201):
                logger.error("Inventory provisioning failed: status=%s body=%s", resp.status_code, resp.text)
                # Roll back catalog event to prevent inconsistency
                event.delete()
                from rest_framework.response import Response
                from rest_framework import status as drf_status
                return Response({"error": "Inventory provisioning failed", "detail": resp.text}, status=drf_status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error provisioning event in Inventory", exc_info=exc)
            event.delete()
            from rest_framework.response import Response
            from rest_framework import status as drf_status
            return Response({"error": "Inventory provisioning error", "detail": str(exc)}, status=drf_status.HTTP_502_BAD_GATEWAY)

        # Return created catalog event
        from rest_framework.response import Response
        from rest_framework import status as drf_status
        return Response(self.get_serializer(event).data, status=drf_status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # Admin-only enforced by get_permissions
        partial = kwargs.pop('partial', True)
        instance = self.get_object()

        allowed_fields = {'price_cents'}
        if any(field not in allowed_fields for field in request.data.keys()):
            return Response({"error": "Only price_cents can be updated"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        # Delete in Inventory first to keep services in sync
        event = self.get_object()
        inventory_base = os.environ.get("INVENTORY_HTTP_BASE", "http://inventory:8003")
        inventory_url = f"{inventory_base}/api/v1/events/{event.id}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.delete(inventory_url)
            if resp.status_code not in (200, 204, 404):
                return Response({"error": "Inventory delete failed", "detail": resp.text}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:  # noqa: BLE001
            return Response({"error": "Inventory delete error", "detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        # Remove from catalog and return a confirmation payload
        self.perform_destroy(event)
        return Response({"status": "deleted", "id": str(event.id)}, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        event = self.get_object()
        serializer = self.get_serializer(event)
        data = serializer.data

        counts = get_inventory_counts(
            str(event.id),
            {
                'tickets_held': event.tickets_held,
                'tickets_sold': event.tickets_sold,
                'total_tickets': event.total_tickets,
            },
        )
        data.update(counts)
        return Response(data)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        events = list(queryset)
        serialized = self.get_serializer(events, many=True).data

        for item, event in zip(serialized, events):
            counts = get_inventory_counts(
                str(event.id),
                {
                    'tickets_held': event.tickets_held,
                    'tickets_sold': event.tickets_sold,
                    'total_tickets': event.total_tickets,
                },
            )
            item.update(counts)

        from rest_framework.response import Response
        return Response(serialized)

