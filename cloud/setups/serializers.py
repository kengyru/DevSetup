"""Serializers for the setup API.

The client is untrusted: every payload goes through
``setups.schema.validate_setup_payload`` before it is stored. Unknown
fields are dropped, unsafe entries are filtered and secrets never reach
the database.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Setup
from .schema import SetupValidationError, validate_setup_payload

MAX_SETUPS_PER_USER = 50

User = get_user_model()


class SetupListSerializer(serializers.ModelSerializer):
    """List representation: metadata only, never the full JSON."""

    class Meta:
        model = Setup
        fields = (
            "id",
            "name",
            "format_version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SetupDetailSerializer(serializers.ModelSerializer):
    """Create/update/retrieve representation including sanitized data."""

    data = serializers.JSONField()

    class Meta:
        model = Setup
        fields = (
            "id",
            "name",
            "format_version",
            "data",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "format_version",
            "created_at",
            "updated_at",
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "This field may not be blank."
            )

        return value

    def validate_data(self, value):
        try:
            payload = validate_setup_payload(value)
        except SetupValidationError as error:
            raise serializers.ValidationError(
                error.detail
            ) from error

        self._sanitized_payload = payload
        return payload.data

    def validate(self, attrs):
        payload = getattr(self, "_sanitized_payload", None)

        if payload is None:
            # ``data`` is required for both create and full update. DRF
            # already returns a field error in that case; this guard only
            # protects against accidental partial updates.
            raise serializers.ValidationError(
                {"data": ["This field is required."]}
            )

        attrs["format_version"] = payload.format_version
        return attrs

    def create(self, validated_data):
        user = validated_data["user"]

        with transaction.atomic():
            # Lock the owner row so two simultaneous requests cannot both
            # pass the 50 setups limit.
            User.objects.select_for_update().get(pk=user.pk)

            current = Setup.objects.filter(user=user).count()

            if current >= MAX_SETUPS_PER_USER:
                raise serializers.ValidationError(
                    {
                        "detail": (
                            "Each user can store at most "
                            f"{MAX_SETUPS_PER_USER} setups."
                        )
                    }
                )

            return super().create(validated_data)
