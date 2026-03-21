"""
User serializers — registration, auth, profile management.
"""
import re
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Address, PaymentMethod


class AddressSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=50, default='Home')
    recipient_name = serializers.CharField(max_length=200)
    postal_code = serializers.CharField(max_length=20)
    city = serializers.CharField(max_length=100)
    street = serializers.CharField(max_length=500)
    building = serializers.CharField(max_length=200, allow_blank=True, required=False)
    country = serializers.CharField(max_length=100)
    country_code = serializers.CharField(max_length=3, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)
    is_default = serializers.BooleanField(default=False)


class PaymentMethodSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=200)
    type = serializers.ChoiceField(choices=['card', 'paypal', 'bank_transfer', 'gcash', 'other'])
    brand = serializers.CharField(max_length=20, allow_blank=True, required=False)
    last4 = serializers.CharField(max_length=4, allow_blank=True, required=False)
    expiry = serializers.CharField(max_length=7, allow_blank=True, required=False)
    holder_name = serializers.CharField(max_length=200, allow_blank=True, required=False)
    is_default = serializers.BooleanField(default=False)


class UserRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    phone_number = serializers.CharField(max_length=30, allow_blank=True, required=False)

    def validate_username(self, value):
        if not re.match(r'^[a-zA-Z0-9_.-]+$', value):
            raise serializers.ValidationError(
                'Username may only contain letters, numbers, underscores, hyphens, and dots.'
            )
        if User.objects(username=value).first():
            raise serializers.ValidationError('Username already taken.')
        return value

    def validate_email(self, value):
        if User.objects(email=value.lower()).first():
            raise serializers.ValidationError('Email already registered.')
        return value.lower()

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def validate_password(self, value):
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'\d', value):
            raise serializers.ValidationError('Password must contain at least one number.')
        return value

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data.get('phone_number', ''),
        )
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserProfileSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    phone_number = serializers.CharField(max_length=30, allow_blank=True, required=False)
    avatar_url = serializers.URLField(allow_blank=True, required=False)
    preferred_locale = serializers.ChoiceField(choices=['en', 'ja'], required=False)
    preferred_currency = serializers.CharField(max_length=3, required=False)
    is_verified = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)
    payment_methods = PaymentMethodSerializer(many=True, read_only=True)
    wishlist = serializers.ListField(child=serializers.CharField(), read_only=True)

    def get_id(self, obj):
        return str(obj.id)

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match.'})
        return data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extends JWT payload with user info for MongoEngine User model."""
    
    def validate(self, attrs):
        """
        Validate MongoEngine user credentials.
        attrs: dict with 'email'/'username' and 'password' keys.
        """
        from .services import authenticate_user
        from django.contrib.auth.models import update_last_login
        from rest_framework_simplejwt.authentication import JWTAuthentication
        
        # Support both email and username for login
        email = attrs.get('email') or attrs.get('username')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError(
                {'detail': 'Must include "email" and "password".'}
            )
        
        # Authenticate using MongoEngine User model
        user = authenticate_user(email, password)
        if not user:
            raise serializers.ValidationError(
                {'detail': 'Invalid credentials.'}
            )
        
        # Generate tokens for the authenticated user
        tokens = self.get_token(user)
        
        return {
            'access': str(tokens['access']),
            'refresh': str(tokens['refresh']),
        }
    
    @classmethod
    def get_token(cls, user):
        """Create JWT token for MongoEngine user."""
        # Manually create tokens since we can't use super().get_token() 
        # which expects Django User model
        from rest_framework_simplejwt.tokens import RefreshToken
        
        refresh = RefreshToken()
        refresh['user_id'] = str(user.id)
        refresh['username'] = user.username
        refresh['email'] = user.email
        refresh['is_staff'] = user.is_staff
        
        return {
            'refresh': refresh,
            'access': refresh.access_token,
        }


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """Custom token refresh serializer for MongoEngine User model."""
    
    def validate(self, attrs):
        """
        Validate refresh token for MongoEngine User.
        The default implementation tries to use Django's User model.
        """
        refresh = RefreshToken(attrs['refresh'])
        
        data = {
            'access': str(refresh.access_token),
        }
        
        return data
    

class AdminUserSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    phone_number = serializers.CharField(max_length=30, allow_blank=True, required=False)
    is_staff = serializers.BooleanField(required=False)

    def get_id(self, obj):
        return str(obj.id)