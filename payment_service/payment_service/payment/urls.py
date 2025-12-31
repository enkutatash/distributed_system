from django.urls import path
from .views import PaymentCreateView, StripeWebhookView, payment_success, payment_cancel

urlpatterns = [
    path('api/v1/payments/', PaymentCreateView.as_view(), name='payment-create'),
    path('api/v1/payments/webhook/', StripeWebhookView.as_view(), name='payment-webhook'),
    path('payment/success/', payment_success, name='payment-success'),
    path('payment/cancel/', payment_cancel, name='payment-cancel'),
]
