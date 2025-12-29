from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from .models import AuthToken


class TokenAuthentication(BaseAuthentication):
    """
    Custom authentication class for Bearer Token (non-expiring)
    Usage: Authorization: Bearer <token_string>
    """
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return None  # No token → unauthenticated (not unauthorized)

        if not auth_header.startswith('Bearer '):
            raise AuthenticationFailed('Invalid token header. Use Bearer <token>.')

        token = auth_header.split(' ')[1]

        try:
            auth_token = AuthToken.objects.select_related('user').get(token=token)
            # Update last_used_at
            auth_token.last_used_at = timezone.now()
            auth_token.save(update_fields=['last_used_at'])

            # Return (user, token_object) as expected by DRF
            return (auth_token.user, auth_token)

        except AuthToken.DoesNotExist:
            raise AuthenticationFailed('Invalid token')
        except IndexError:
            raise AuthenticationFailed('Invalid token header format')