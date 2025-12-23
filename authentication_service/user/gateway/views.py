# gateway/views.py

import httpx
import json
from django.utils import timezone
from urllib.parse import urljoin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from authentication.models import AuthToken


class ProxyView(APIView):
    """
    Generic proxy view that forwards requests to internal services.
    Handles authentication, user forwarding, and proper response rendering.
    """
    internal_url = ""        # e.g., "http://localhost:8001/api/v1"
    require_auth = True      # Set to False for fully public services

    def dispatch(self, request, *args, **kwargs):
        # Mirror DRF's dispatch to ensure headers and renderers are set
        request = self.initialize_request(request, *args, **kwargs)
        self.request = request
        self.headers = self.default_response_headers
        try:
            self.initial(request, *args, **kwargs)
            response = self.proxy_request(request)
        except Exception as exc:  # noqa: BLE001
            response = self.handle_exception(exc)
        return self.finalize_response(request, response, *args, **kwargs)

    def proxy_request(self, request):
        # Prepare auth variables
        token = None
        auth_token = None
        user_id = None
        is_staff = False

        # === 1. Extract Authorization token if present (don't require it yet) ===
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            try:
                auth_token = AuthToken.objects.select_related('user').get(token=token)
                user_id = str(auth_token.user.id)
                is_staff = auth_token.user.is_staff  # For admin checks
                auth_token.last_used_at = timezone.now()
                auth_token.save(update_fields=['last_used_at'])
            except AuthToken.DoesNotExist:
                # leave auth_token as None — we'll enforce below if required
                auth_token = None

        # If this proxy requires authentication, enforce presence of a valid token
        # Avoid crashing when no token is provided by safely stringifying it
        print(f"token is here {token}")
        if self.require_auth:
            if not token or not auth_token:
                return Response(
                    {"error": "Authentication credentials were not provided."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        # === 2. Admin-only check for event creation ===
        # Block non-admin users from creating events
        if request.path.startswith('/api/v1/events/') and request.method == 'POST':
            if not is_staff:
                return Response(
                    {"error": "Admin access required to create."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # === 3. Build internal URL cleanly ===
        # Use urljoin to safely combine base + request path
        # This avoids duplicate /api/v1 or wrong slashes
        full_path = request.get_full_path()  # includes query string, e.g. /api/v1/events/?page=2
        internal_url = urljoin(self.internal_url + '/', full_path.lstrip('/api/v1'))
        # Result: http://localhost:8001/api/v1/events/?page=2

        # === 4. Prepare headers for internal service ===
        # Forward most incoming headers to the internal service.
        # Keep the Authorization header so internal services that require
        # authentication (e.g. creating events) receive the token.

        forward_headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in ['host', 'content-length']
        }
        if user_id:
            forward_headers['X-User-ID'] = user_id

        # === 5. Forward the request ===
        try:
            with httpx.Client(timeout=10.0) as client:
                print(f"[gateway] forwarding: method={request.method} url={internal_url}")
                resp = client.request(
                    method=request.method,
                    url=internal_url,
                    headers=forward_headers,
                    content=request.body,
                    params=request.GET,  # already in full_path, but safe
                )
                print(f"[gateway] proxied response: status={resp.status_code} content_type={resp.headers.get('Content-Type')}")

            # === 6. Return correct response type ===
            content_type = resp.headers.get('Content-Type', '')

            # Always return a raw HttpResponse for proxied content to avoid
            # DRF renderer lifecycle issues (Response.accepted_renderer not set).
            proxy_response = HttpResponse(
                content=resp.content,
                status=resp.status_code,
                content_type=content_type or 'application/octet-stream'
            )
            # Optional debug header to see actual internal route used
            proxy_response['X-Proxied-URL'] = internal_url
            return proxy_response

        except httpx.RequestError as exc:
            body = json.dumps({"error": "Unable to reach internal service", "detail": str(exc)})
            return HttpResponse(body, status=status.HTTP_503_SERVICE_UNAVAILABLE, content_type='application/json')


# Public Catalog Service (read-only public, create protected by admin check above)
class CatalogProxy(ProxyView):
    internal_url = "http://localhost:8002/api/v1"
    require_auth = False  # Read access is public


# Protected Booking Service
class BookingProxy(ProxyView):
    internal_url = "http://localhost:8001/api/v1"
    require_auth = True