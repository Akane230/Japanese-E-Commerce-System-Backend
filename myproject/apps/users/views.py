"""
Auth and user profile API views.
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer,
    UserProfileSerializer, ChangePasswordSerializer, AddressSerializer
)
from .services import authenticate_user, get_tokens_for_user

logger = logging.getLogger(__name__)


class AuthRateThrottle(AnonRateThrottle):
    scope = 'auth'


def success_response(data=None, message='', status_code=200):
    return Response({
        'success': True,
        'message': message,
        'data': data or {},
    }, status=status_code)


def get_mongo_user(request) -> User:
    """Get MongoEngine User from JWT user_id."""
    user_id = request.user.id
    return User.objects(id=user_id).first()


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def register(request):
    """POST /api/auth/register"""
    serializer = UserRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors}, status=400)

    user = serializer.create(serializer.validated_data)
    tokens = get_tokens_for_user(user)

    return success_response({
        'user': {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
        },
        'tokens': tokens,
    }, message='Account created successfully.', status_code=201)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def login(request):
    """POST /api/auth/login"""
    serializer = UserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors}, status=400)

    user = authenticate_user(
        serializer.validated_data['email'],
        serializer.validated_data['password']
    )
    if not user:
        return Response({
            'success': False,
            'message': 'Invalid email or password.',
        }, status=401)

    tokens = get_tokens_for_user(user)
    profile = UserProfileSerializer(user)

    return success_response({
        'user': profile.data,
        'tokens': tokens,
    }, message='Login successful.')


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    """POST /api/auth/logout — blacklist refresh token"""
    refresh_token = request.data.get('refresh')
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
    return success_response(message='Logged out successfully.')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """POST /api/auth/change-password"""
    user = get_mongo_user(request)
    serializer = ChangePasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors}, status=400)

    if not user.check_password(serializer.validated_data['current_password']):
        return Response({'success': False, 'message': 'Current password is incorrect.'}, status=400)

    user.set_password(serializer.validated_data['new_password'])
    user.save()
    return success_response(message='Password changed successfully.')