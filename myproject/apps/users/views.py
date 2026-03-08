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
from .services import authenticate_user, get_tokens_for_user, toggle_wishlist, add_address

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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/auth/me — current user profile"""
    user = get_mongo_user(request)
    if not user:
        return Response({'success': False, 'message': 'User not found.'}, status=404)

    return success_response(UserProfileSerializer(user).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """PUT /api/auth/profile"""
    user = get_mongo_user(request)
    if not user:
        return Response({'success': False, 'message': 'User not found.'}, status=404)

    serializer = UserProfileSerializer(user, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors}, status=400)

    updated_user = serializer.update(user, serializer.validated_data)
    return success_response(UserProfileSerializer(updated_user).data, message='Profile updated.')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_address_view(request):
    """POST /api/auth/addresses"""
    user = get_mongo_user(request)
    serializer = AddressSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors}, status=400)

    user = add_address(user, serializer.validated_data)
    return success_response(
        [a.to_dict() for a in user.addresses],
        message='Address added.',
        status_code=201
    )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_address_view(request, idx):
    """DELETE /api/auth/addresses/<idx>"""
    user = get_mongo_user(request)
    if idx >= len(user.addresses):
        return Response({'success': False, 'message': 'Address not found.'}, status=404)
    user.addresses.pop(idx)
    user.save()
    return success_response([a.to_dict() for a in user.addresses], message='Address removed.')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_wishlist_view(request, product_id):
    """POST /api/auth/wishlist/<product_id>"""
    user = get_mongo_user(request)
    user, added = toggle_wishlist(user, product_id)
    return success_response(
        {'wishlist': user.wishlist, 'added': added},
        message='Wishlist updated.'
    )