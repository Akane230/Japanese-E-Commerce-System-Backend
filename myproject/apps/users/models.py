"""
User models using MongoEngine for MongoDB.
Supports international customers with multiple addresses and payment methods.
"""
import bcrypt
from datetime import datetime
from mongoengine import (
    Document, EmbeddedDocument, StringField, EmailField,
    BooleanField, DateTimeField, ListField, EmbeddedDocumentField,
    URLField, IntField, ObjectIdField
)


class Address(EmbeddedDocument):
    """International shipping address."""
    label = StringField(max_length=50, default='Home')           # Home, Work, Other
    recipient_name = StringField(max_length=200, required=True)
    postal_code = StringField(max_length=20, required=True)
    city = StringField(max_length=100, required=True)
    street = StringField(max_length=500, required=True)
    building = StringField(max_length=200)                        # Apartment, suite, etc.
    country = StringField(max_length=100, required=True)          # ISO country name
    country_code = StringField(max_length=3)                      # ISO 3166-1 alpha-2
    phone = StringField(max_length=30)
    is_default = BooleanField(default=False)

    def to_dict(self):
        return {
            'label': self.label,
            'recipient_name': self.recipient_name,
            'postal_code': self.postal_code,
            'city': self.city,
            'street': self.street,
            'building': self.building,
            'country': self.country,
            'country_code': self.country_code,
            'phone': self.phone,
            'is_default': self.is_default,
        }


class PaymentMethod(EmbeddedDocument):
    """Saved payment method (tokenized — never store raw card data)."""
    id = StringField(required=True)                 # Stripe/PayPal token
    type = StringField(
        max_length=20,
        choices=['card', 'paypal', 'bank_transfer', 'gcash', 'other'],
        default='card'
    )
    brand = StringField(max_length=20)              # visa, mastercard, amex
    last4 = StringField(max_length=4)
    expiry = StringField(max_length=7)              # MM/YYYY
    holder_name = StringField(max_length=200)
    is_default = BooleanField(default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'brand': self.brand,
            'last4': self.last4,
            'expiry': self.expiry,
            'holder_name': self.holder_name,
            'is_default': self.is_default,
        }


class User(Document):
    """
    Main user document.
    Supports international customers purchasing Japanese products.
    """
    # Identity
    username = StringField(max_length=150, required=True, unique=True)
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)

    # Profile
    first_name = StringField(max_length=100)
    last_name = StringField(max_length=100)
    avatar_url = URLField()
    phone_number = StringField(max_length=30)
    date_of_birth = DateTimeField()

    # Location info (derived from preferred shipping address)
    preferred_locale = StringField(max_length=10, default='en')   # en, ja
    preferred_currency = StringField(max_length=3, default='USD')

    # Embedded documents
    addresses = ListField(EmbeddedDocumentField(Address))
    payment_methods = ListField(EmbeddedDocumentField(PaymentMethod))
    wishlist = ListField(StringField())  # product_ids as strings

    # Account status
    is_active = BooleanField(default=True)
    is_staff = BooleanField(default=False)
    is_verified = BooleanField(default=False)
    email_verified_at = DateTimeField()

    # compatibility with Django auth
    @property
    def is_authenticated(self):
        """Always True for authenticated users (required by DRF throttling)."""
        return True

    # Timestamps
    last_login = DateTimeField()
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'users',
        'indexes': [
            {'fields': ['email'], 'unique': True},
            {'fields': ['username'], 'unique': True},
            {'fields': ['created_at']},
        ],
        'ordering': ['-created_at'],
    }

    def set_password(self, raw_password: str) -> None:
        """Hash and store password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(
            raw_password.encode('utf-8'), salt
        ).decode('utf-8')

    def check_password(self, raw_password: str) -> bool:
        """Verify password against stored hash."""
        try:
            return bcrypt.checkpw(
                raw_password.encode('utf-8'),
                self.password_hash.encode('utf-8')
            )
        except Exception:
            return False

    def get_full_name(self) -> str:
        return f'{self.first_name or ""} {self.last_name or ""}'.strip()

    def get_default_address(self):
        for addr in self.addresses:
            if addr.is_default:
                return addr
        return self.addresses[0] if self.addresses else None

    def get_default_payment_method(self):
        for pm in self.payment_methods:
            if pm.is_default:
                return pm
        return self.payment_methods[0] if self.payment_methods else None

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.username} <{self.email}>'