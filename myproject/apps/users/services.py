"""
User business logic — auth, JWT helpers, profile ops.
"""
import logging
from datetime import datetime
from typing import Optional, Tuple
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User

logger = logging.getLogger(__name__)


def get_tokens_for_user(user: User) -> dict:
    """Generate JWT access + refresh token pair for a MongoEngine User."""

    from rest_framework_simplejwt.tokens import RefreshToken

    # Create a refresh token without using for_user()
    refresh = RefreshToken()
    refresh['user_id'] = str(user.id)
    refresh['username'] = user.username
    refresh['email'] = user.email
    refresh['is_staff'] = user.is_staff

    # Create access token from refresh token
    access = refresh.access_token
    access['user_id'] = str(user.id)
    access['username'] = user.username
    access['email'] = user.email
    access['is_staff'] = user.is_staff

    return {
        'access': str(access),
        'refresh': str(refresh),
    }


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Validate email+password, return User or None."""
    try:
        user = User.objects(email=email.lower(), is_active=True).first()
        if user and user.check_password(password):
            user.last_login = datetime.utcnow()
            user.save()
            return user
    except Exception as e:
        logger.exception(f'Authentication error for {email}: {e}')
    return None


def get_user_from_token_payload(payload: dict) -> Optional[User]:
    """Extract user from JWT payload user_id."""
    user_id = payload.get('user_id')
    if not user_id:
        return None
    try:
        return User.objects(id=user_id, is_active=True).first()
    except Exception:
        return None


def add_address(user: User, address_data: dict) -> User:
    from .models import Address
    addr = Address(**address_data)
    if addr.is_default:
        for a in user.addresses:
            a.is_default = False
    user.addresses.append(addr)
    user.save()
    return user


def remove_address(user: User, idx: int) -> User:
    if 0 <= idx < len(user.addresses):
        user.addresses.pop(idx)
    user.save()
    return user


def toggle_wishlist(user: User, product_id: str) -> Tuple[User, bool]:
    """Returns (user, added). added=True means just added, False=removed."""
    pid = str(product_id)
    if pid in user.wishlist:
        user.wishlist.remove(pid)
        added = False
    else:
        user.wishlist.append(pid)
        added = True
    user.save()
    return user, added