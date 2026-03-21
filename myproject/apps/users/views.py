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

from config.exceptions import success_response as base_success_response, error_response
from apps.cart.services import CART_SESSION_KEY

from .models import User
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    AddressSerializer,
    AdminUserSerializer,
)
from .services import authenticate_user, get_tokens_for_user, toggle_wishlist, add_address, remove_address
from apps.cart.services import merge_carts, get_session_cart, get_or_create_user_cart


logger = logging.getLogger(__name__)


class AuthRateThrottle(AnonRateThrottle):
    scope = 'auth'


def success_response(data=None, message='', status_code=200):
    # wrapper around the imported helper; use a distinct name to avoid
    # recursive calls (the original code shadowed the imported symbol).
    return base_success_response(
        data=data,
        message=message,
        status_code=status_code,
    )


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
        return error_response(
            error='ValidationError',
            message='Invalid registration data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

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
        return error_response(
            error='ValidationError',
            message='Invalid login data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    user = authenticate_user(
        serializer.validated_data['email'],
        serializer.validated_data['password']
    )
    if not user:
        return error_response(
            error='Unauthorized',
            message='Invalid email or password.',
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    
    session_cart = get_session_cart(request)
    if session_cart:  # Guest has items in cart
        user_cart = get_or_create_user_cart(str(user.id))
        merge_carts(session_cart, user_cart)
        # Clear session cart after merge
        request.session[CART_SESSION_KEY] = {}
        request.session.modified = True

    tokens = get_tokens_for_user(user)
    profile = UserProfileSerializer(user)

    return success_response({
        'user': profile.data,
        'tokens': tokens,
    }, message='Login successful.')

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def adminLogin(request):
    """POST /api/auth/admin-login"""
    serializer = UserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid login data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    user = authenticate_user(
        serializer.validated_data['email'],
        serializer.validated_data['password']
    )
    if not user or not user.is_staff:
        return error_response(
            error='Unauthorized',
            message='Invalid email or password, or not an admin.',
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    tokens = get_tokens_for_user(user)
    profile = AdminUserSerializer(user)

    return success_response({
        'user': profile.data,
        'tokens': tokens,
    }, message='Admin login successful.')

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
        return error_response(
            error='ValidationError',
            message='Invalid password data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    if not user.check_password(serializer.validated_data['current_password']):
        return error_response(
            error='Bad Request',
            message='Current password is incorrect.',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(serializer.validated_data['new_password'])
    user.save()
    return success_response(message='Password changed successfully.')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/auth/me — current user profile"""
    user = get_mongo_user(request)
    if not user:
        return error_response(
            error='NotFound',
            message='User not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(UserProfileSerializer(user).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """PUT /api/auth/profile"""
    user = get_mongo_user(request)
    if not user:
        return error_response(
            error='NotFound',
            message='User not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    serializer = UserProfileSerializer(user, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid profile data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    updated_user = serializer.update(user, serializer.validated_data)
    return success_response(UserProfileSerializer(updated_user).data, message='Profile updated.')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_address_view(request):
    """POST /api/auth/addresses"""
    user = get_mongo_user(request)
    serializer = AddressSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid address data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

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
    try:
        user = remove_address(user, int(idx))
        return success_response([a.to_dict() for a in user.addresses], message='Address removed.')
    except (ValueError, IndexError):
        return error_response(
            error='NotFound',
            message='Address not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )


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

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_address_view(request, idx):
    """DELETE /api/auth/addresses/<idx>"""
    user = get_mongo_user(request)
    try:
        user = remove_address(user, int(idx))
        return success_response([a.to_dict() for a in user.addresses], message='Address removed.')
    except (ValueError, IndexError):
        return error_response(
            error='NotFound',
            message='Address not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )
 
 
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_address_view(request, idx):
    """PUT /api/auth/addresses/<idx>/ — update address fields by index"""
    user = get_mongo_user(request)
    try:
        index = int(idx)
        if index < 0 or index >= len(user.addresses):
            raise IndexError
    except (ValueError, IndexError):
        return error_response(
            error='NotFound',
            message='Address not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )
 
    serializer = AddressSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid address data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )
 
    addr = user.addresses[index]
    for field, value in serializer.validated_data.items():
        setattr(addr, field, value)
 
    # If setting this address as default, clear others
    if serializer.validated_data.get('is_default'):
        for i, a in enumerate(user.addresses):
            if i != index:
                a.is_default = False
 
    user.save()
    return success_response(
        [a.to_dict() for a in user.addresses],
        message='Address updated.',
    )
 
 
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_default_address_view(request, idx):
    """POST /api/auth/addresses/<idx>/set-default/ — mark one address as default"""
    user = get_mongo_user(request)
    try:
        index = int(idx)
        if index < 0 or index >= len(user.addresses):
            raise IndexError
    except (ValueError, IndexError):
        return error_response(
            error='NotFound',
            message='Address not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )
 
    for i, a in enumerate(user.addresses):
        a.is_default = (i == index)
 
    user.save()
    return success_response(
        [a.to_dict() for a in user.addresses],
        message='Default address updated.',
    )
 
 
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