from rest_framework import mixins, viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Event
from .serializers import EventProvisionSerializer


class EventProvisionViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
	queryset = Event.objects.all()
	serializer_class = EventProvisionSerializer
	permission_classes = [AllowAny]

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		data = serializer.validated_data

		# Create or update total_tickets for given UUID
		event, created = Event.objects.update_or_create(
			id=data["id"],
			defaults={"total_tickets": data["total_tickets"]},
		)
		return Response({
			"id": str(event.id),
			"total_tickets": event.total_tickets,
			"created": created,
		}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
