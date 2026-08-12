from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.models import AuditLog
from apps.users.serializers import RegisterSerializer, UserSerializer


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — create a new user account."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        AuditLog.objects.create(
            user=user, action="user.registered", resource_type="User",
            resource_id=str(user.id), ip_address=_client_ip(request),
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — obtain access + refresh JWT pair."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            username = request.data.get("username", "")
            AuditLog.objects.create(
                action="user.login", resource_type="User",
                resource_id=username, ip_address=_client_ip(request),
            )
        return response


class LogoutView(APIView):
    """
    POST /api/auth/logout/ — blacklist the given refresh token.

    Body: {"refresh": "<refresh_token>"}
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except TokenError:
            return Response({"detail": "Invalid or already-expired refresh token."}, status=status.HTTP_400_BAD_REQUEST)

        AuditLog.objects.create(
            user=request.user, action="user.logout", resource_type="User",
            resource_id=str(request.user.id), ip_address=_client_ip(request),
        )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveAPIView):
    """GET /api/me/ — the authenticated user's own profile."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
