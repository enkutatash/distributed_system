# catalog/authentication.py

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import httpx  # or requests

# Since Auth is in Gateway, call Gateway to validate token (container-to-container)
import os

AUTH_SERVICE_VALIDATE = os.environ.get(
    "AUTH_VALIDATE_URL",
    "http://gateway:8000/api/v1/token/validate/",
)


class GatewayTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ', 1)[1]

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    AUTH_SERVICE_VALIDATE,
                    headers={"Authorization": f"Bearer {token}"},
                )
        except Exception as exc:
            # If auth service is unreachable and this is a safe method, fall back to anonymous
            # Emit a debug print to trace the failure.
            print(f"[catalog auth] validator call failed url={AUTH_SERVICE_VALIDATE} error={exc}")
            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                return None
            raise AuthenticationFailed(f"Auth service unreachable: {exc}")

        if response.status_code != 200:
            # Allow reads to proceed anonymously if token fails; writes still fail
            print(f"[catalog auth] validator status={response.status_code} body={response.text}")
            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                return None
            raise AuthenticationFailed(f"Invalid token (status {response.status_code})")

        data = response.json()
        # Construct a lightweight user-like object
        class RemoteUser:
            def __init__(self, user_id, is_staff=False):
                self.id = user_id
                self.is_staff = is_staff
                self.is_authenticated = True

        try:
            print(f"[catalog auth] validator ok is_staff={data.get('is_staff')} user_id={data.get('user_id')}")
        except Exception:
            pass

        return (RemoteUser(data.get('user_id'), data.get('is_staff', False)), None)