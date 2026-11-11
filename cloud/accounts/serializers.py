"""Serializers for registration and user representation."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user. Never includes the password."""

    class Meta:
        model = User
        fields = ("id", "email", "created_at")
        read_only_fields = fields


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login serializer that treats the email as case-insensitive."""

    def validate(self, attrs):
        email = attrs.get(self.username_field)

        if isinstance(email, str):
            attrs[self.username_field] = email.strip().lower()

        return super().validate(attrs)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return email

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                list(error.messages)
            ) from error

        return value

    def create(self, validated_data):
        try:
            return User.objects.create_user(
                email=validated_data["email"],
                password=validated_data["password"],
            )
        except IntegrityError as error:
            # Covers the race between validate_email and the INSERT.
            raise serializers.ValidationError(
                {
                    "email": [
                        "A user with this email already exists."
                    ]
                }
            ) from error
