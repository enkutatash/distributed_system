from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

class TemporaryTokenAuth(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]
        # Temporary: just accept any non-empty token and fake user_id
        if token:
            return ('user_from_token', None)  # (user, auth)

        raise AuthenticationFailed('Invalid token')

    def authenticate_header(self, request):
        return 'Bearer'