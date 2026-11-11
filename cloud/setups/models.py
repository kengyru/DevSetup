"""Stored development environments."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Setup(models.Model):
    """A user owned .setup payload.

    ``data`` contains only the sanitized environment description; it is
    never executed. The owner is always taken from the authenticated
    request, never from the client payload.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="setups",
    )
    name = models.CharField(max_length=100)
    format_version = models.PositiveSmallIntegerField()
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="setups_user_created_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(format_version__in=(1, 2)),
                name="setups_format_version_1_or_2",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.user_id})"
