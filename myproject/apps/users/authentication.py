"""
Custom JWT authentication for MongoEngine User model.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from django.utils.translation import gettext_lazy as _
from .models import User


class MongoEngineJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that works with MongoEngine User model.
    """

    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_('Token contained no recognizable user identification'))

        try:
            # Use MongoEngine to find the user by ID (ObjectId string)
            user = User.objects(id=user_id, is_active=True).first()
        except Exception:
            raise InvalidToken(_('User not found'))

        if user is None:
            raise InvalidToken(_('User not found'))

        return user