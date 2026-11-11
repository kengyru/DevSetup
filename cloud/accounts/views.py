"""Authentication endpoints: register, login and refresh."""

from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .serializers import (
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    """Create an account. Returns the user, never the password."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = serializer.save()
        except IntegrityError:
            return Response(
                {
                    "email": [
                        "A user with this email already exists."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """Return a short lived access token and a long lived refresh token."""

    serializer_class = EmailTokenObtainPairSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"


class RefreshView(TokenRefreshView):
    """Rotate a refresh token and return a new access token."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"
