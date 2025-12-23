from rest_framework import viewsets, mixins
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

logger = logging.getLogger(__name__)

class EventViewSet(mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.CreateModelMixin,
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
            with httpx.Client(timeout=5.0) as client:
                resp = client.post("http://localhost:8004/api/v1/events", json=payload)
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

