from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReservationViewSet

router = DefaultRouter()
router.register(r'reservations', ReservationViewSet, basename='reservation')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/reservations/<uuid:pk>/cancel/', ReservationViewSet.as_view({'post': 'cancel'}), name='reservation-cancel'),
]