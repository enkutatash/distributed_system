from django.urls import path
from .views import PaymentCreateView, StripeWebhookView

urlpatterns = [
    path('api/v1/payments/', PaymentCreateView.as_view(), name='payment-create'),
    path('api/v1/payments/webhook/', StripeWebhookView.as_view(), name='payment-webhook'),
]
