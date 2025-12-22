from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import User, AuthToken
from django.contrib.auth.hashers import make_password
from django.utils import timezone
import secrets

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')

        if not username or not password:
            return Response({'error': 'username and password required'}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already taken'}, status=400)

        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)
        user.save()

        # Generate non-expiring token
        token = secrets.token_urlsafe(64)
        AuthToken.objects.create(user=user, token=token, name="Initial Token")

        return Response({
            'user_id': str(user.id),
            'username': user.username,
            'token': token
        }, status=201)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                # Create new token on login
                token = secrets.token_urlsafe(64)
                auth_token = AuthToken.objects.create(user=user, token=token, name="Login Token")
                return Response({
                    'user_id': str(user.id),
                    'username': user.username,
                    'token': token
                })
            else:
                return Response({'error': 'Invalid credentials'}, status=401)
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=401)
