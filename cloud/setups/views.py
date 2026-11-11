"""Setup API views.

Every queryset is filtered by ``request.user``. Foreign resources are
indistinguishable from missing ones: both return 404.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Setup
from .serializers import (
    SetupDetailSerializer,
    SetupListSerializer,
)


class SetupViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    # The specification only requires full updates (PUT). PATCH is
    # intentionally not exposed.
    http_method_names = [
        "get",
        "post",
        "put",
        "delete",
        "head",
        "options",
    ]

    # Reject malformed identifiers at the routing layer so an invalid
    # UUID can never reach the ORM and turn into a 500 response.
    lookup_value_regex = (
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )

    def get_queryset(self):
        return Setup.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return SetupListSerializer

        return SetupDetailSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
