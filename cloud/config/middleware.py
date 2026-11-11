"""Small, dependency free request guards."""

from django.conf import settings
from django.http import JsonResponse


class RequestBodyLimitMiddleware:
    """Reject oversized setup uploads before DRF parses the JSON body.

    The setup schema enforces a 2 MB data limit; this middleware protects
    the process from a much larger body that would otherwise be read into
    memory first. Only API writes are checked, so admin uploads and normal
    pages are not affected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in {"POST", "PUT", "PATCH"} and (
            request.path.startswith("/api/setups/")
        ):
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except (TypeError, ValueError):
                length = 0

            if length > settings.MAX_REQUEST_BYTES:
                return JsonResponse(
                    {"detail": "Request body is too large."},
                    status=413,
                )

        return self.get_response(request)
