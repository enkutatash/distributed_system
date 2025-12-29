from django_filters import rest_framework as filters
from .models import Event
from django.utils import timezone

class EventFilter(filters.FilterSet):
    search = filters.CharFilter(field_name='name', lookup_expr='icontains')
    start_after = filters.DateFilter(field_name='start_at', lookup_expr='gte')
    start_before = filters.DateFilter(field_name='start_at', lookup_expr='lte')

    class Meta:
        model = Event
        fields = ['search', 'start_after', 'start_before']

    def filter_queryset(self, queryset):
        # Only show upcoming or ongoing events by default
        queryset = super().filter_queryset(queryset)
        return queryset.filter(start_at__gte=timezone.now())