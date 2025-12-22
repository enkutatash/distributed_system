# gateway/views.py

import httpx
from django.utils import timezone
from urllib.parse import urlparse
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponse
from authentication.models import AuthToken  # Import your AuthToken model

class ProxyView(APIView):
    internal_url = ""  # To be overridden by subclasses
    require_auth = True  # Default: require token (override for public)

    def dispatch(self, request, *args, **kwargs):
        user_id = None

        # Authentication check (only if require_auth is True)
        if self.require_auth:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return Response({"error": "Authentication required"}, status=401)

            token = auth_header.split(' ')[1]
            try:
                auth_token = AuthToken.objects.select_related('user').get(token=token)
                user_id = str(auth_token.user.id)
                auth_token.last_used_at = timezone.now()
                auth_token.save(update_fields=['last_used_at'])
            except AuthToken.DoesNotExist:
                return Response({"error": "Invalid or expired token"}, status=401)

        # Build internal URL
        path = request.path
        # Remove only the leading '/api' prefix so '/api/events/' -> '/events/'
        if path.startswith('/api'):
            target_path = path[len('/api'):]
        else:
            target_path = path

        # Avoid duplicating API version segments. If internal_url contains
        # a version (e.g. '/api/v1') and target_path starts with that same
        # version ('/v1/...'), strip the leading version from target_path.
        internal_path = urlparse(self.internal_url).path
        version_prefix = internal_path.replace('/api', '') if internal_path.startswith('/api') else ''
        if version_prefix and target_path.startswith(version_prefix):
            target_path = target_path[len(version_prefix):]

        if not target_path.startswith('/'):
            target_path = '/' + target_path

        qs = ('?' + request.META['QUERY_STRING']) if request.META.get('QUERY_STRING') else ''
        url = self.internal_url.rstrip('/') + target_path + qs

        # Prepare headers (remove host and content-length; forward others including Content-Type)
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ['host', 'content-length']
        }
        # Add authenticated user ID for internal services
        if user_id:
            headers['X-User-ID'] = user_id

        # Forward the request
        try:
            with httpx.Client() as client:
                response = client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=request.body,
                    timeout=10.0
                )
            # Return a plain HttpResponse for proxied content so DRF's
            # renderer pipeline is not required (avoids .accepted_renderer error).
            proxied = HttpResponse(
                response.content,
                status=response.status_code,
                content_type=response.headers.get('Content-Type', 'application/octet-stream')
            )
            # Add the proxied URL as a debug header to help diagnose routing issues.
            proxied['X-Proxy-URL'] = url
            return proxied
        except httpx.RequestError as e:
            return Response({"error": "Internal service unavailable"}, status=503)


# Protected: Booking Service
class BookingProxy(ProxyView):
    internal_url = "http://localhost:8002/api/v1"
    require_auth = True  # Requires valid Bearer token


# Public: Catalog Service (no auth needed)
class CatalogProxy(ProxyView):
    internal_url = "http://localhost:8001/api/v1"
    require_auth = False  # Public access