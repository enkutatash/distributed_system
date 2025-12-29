"""
URL configuration for user project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
from authentication.views import RegisterView, LoginView, ValidateTokenView
from gateway.views import BookingProxy, CatalogProxy, PaymentProxy


def health_check(_request):
    return HttpResponse("OK", content_type="text/plain")

urlpatterns = [
    path('', health_check),
    path('admin/', admin.site.urls),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('api/v1/token/validate/', ValidateTokenView.as_view()),

    path('api/v1/events/', CatalogProxy.as_view()),
    path('api/v1/events/<path:path>', CatalogProxy.as_view()),

    # Booking
    path('api/v1/reservations/', BookingProxy.as_view()),
    path('api/v1/reservations/<path:path>', BookingProxy.as_view()),

    # Payments
    path('api/v1/payments/', PaymentProxy.as_view()),
    path('api/v1/payments/<path:path>', PaymentProxy.as_view()),
    
]


