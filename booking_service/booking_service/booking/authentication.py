from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from types import SimpleNamespace
import requests


class AuthServiceTokenAuth(BaseAuthentication):
    """Authenticate by delegating token validation to the central auth service.

    Expects the auth service to expose a small validate endpoint at
    http://localhost:8000/api/v1/token/validate/ which returns 200 and
    {'user_id': '<uuid>'} for valid tokens.
    """

    VALIDATE_URL = 'http://localhost:8000/api/v1/token/validate/'

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        try:
            resp = requests.get(self.VALIDATE_URL, headers={'Authorization': auth_header}, timeout=2.0)
        except requests.RequestException:
            raise AuthenticationFailed('Auth service unreachable')

        if resp.status_code == 200:
            data = resp.json()
            user_id = data.get('user_id')
            user = SimpleNamespace(is_authenticated=True, id=user_id)
            request.user_id = str(user_id)
            return (user, None)

        raise AuthenticationFailed('Invalid token')

    def authenticate_header(self, request):
        return 'Bearer'