"""
Order models — full international order lifecycle management.
"""
from datetime import datetime
import random
import string
from mongoengine import (
    Document, EmbeddedDocument, StringField, FloatField, DecimalField,
    IntField, BooleanField, DateTimeField, ListField, EmbeddedDocumentField
)
from django.conf import settings


class OrderItem(EmbeddedDocument):
    product_id = StringField(required=True)
    sku = StringField(max_length=100)
    name = StringField(max_length=500, required=True)
    name_ja = StringField(max_length=500)
    thumbnail = StringField()
    unit_price = DecimalField(required=True, precision=2)
    quantity = IntField(required=True, min_value=1)
    subtotal = DecimalField(required=True, precision=2)
    currency = StringField(max_length=3, default='JPY')

    def to_dict(self):
        return {
            'product_id': self.product_id,
            'sku': self.sku,
            'name': self.name,
            'name_ja': self.name_ja,
            'thumbnail': self.thumbnail,
            'unit_price': float(self.unit_price),
            'quantity': self.quantity,
            'subtotal': float(self.subtotal),
        }


class ShippingAddress(EmbeddedDocument):
    recipient_name = StringField(max_length=200, required=True)
    postal_code = StringField(max_length=20, required=True)
    city = StringField(max_length=100, required=True)
    street = StringField(max_length=500, required=True)
    building = StringField(max_length=200)
    country = StringField(max_length=100, required=True)
    country_code = StringField(max_length=3)
    phone = StringField(max_length=30)

    def to_dict(self):
        return {
            'recipient_name': self.recipient_name,
            'postal_code': self.postal_code,
            'city': self.city,
            'street': self.street,
            'building': self.building,
            'country': self.country,
            'country_code': self.country_code,
            'phone': self.phone,
        }


class PaymentInfo(EmbeddedDocument):
    method = StringField(
        max_length=30,
        choices=['gcash', 'bank_transfer', 'cod', 'maya', 'instapay', 'other'],
        required=True
    )
    status = StringField(
        max_length=20,
        choices=['pending', 'payment_pending', 'paid', 'failed', 'refunded', 'partially_refunded'],
        default='pending'
    )
    # Manual payment fields
    transaction_id = StringField(max_length=200)    # Customer's reference number
    proof_url = StringField(max_length=1000)        # Screenshot/receipt URL
    submitted_at = DateTimeField()                  # When customer submitted proof
    confirmed_by = StringField(max_length=100)      # Admin user_id who confirmed
    confirmed_at = DateTimeField()                  # When admin confirmed
    provider = StringField(max_length=30, default='manual')
    amount = DecimalField(precision=2)
    currency = StringField(max_length=3, default='JPY')
    paid_at = DateTimeField()
    refunded_at = DateTimeField()
    refund_amount = DecimalField(precision=2)
    refund_reference = StringField(max_length=200)  # Reference of refund transfer
    failure_reason = StringField(max_length=500)

    def to_dict(self):
        return {
            'method': self.method,
            'status': self.status,
            'transaction_id': self.transaction_id,
            'proof_url': self.proof_url,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'amount': float(self.amount) if self.amount else None,
            'currency': self.currency,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'refunded_at': self.refunded_at.isoformat() if self.refunded_at else None,
            'refund_amount': float(self.refund_amount) if self.refund_amount else None,
        }


class ShippingInfo(EmbeddedDocument):
    carrier = StringField(max_length=100)           # Japan Post EMS, DHL, FedEx
    service = StringField(max_length=100)            # EMS, Standard, Express
    tracking_number = StringField(max_length=200)
    tracking_url = StringField(max_length=500)
    estimated_delivery = DateTimeField()
    shipped_at = DateTimeField()
    delivered_at = DateTimeField()
    weight_kg = FloatField()
    shipping_cost = DecimalField(precision=2)

    def to_dict(self):
        return {
            'carrier': self.carrier,
            'service': self.service,
            'tracking_number': self.tracking_number,
            'tracking_url': self.tracking_url,
            'estimated_delivery': self.estimated_delivery.isoformat() if self.estimated_delivery else None,
            'shipped_at': self.shipped_at.isoformat() if self.shipped_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
        }


class StatusHistory(EmbeddedDocument):
    status = StringField(required=True)
    label = StringField(max_length=200)
    note = StringField(max_length=1000)
    actor = StringField(max_length=100, default='system')  # user_id or 'system'
    timestamp = DateTimeField(default=datetime.utcnow)

    def to_dict(self):
        return {
            'status': self.status,
            'label': self.label,
            'note': self.note,
            'timestamp': self.timestamp.isoformat(),
        }


ORDER_STATUSES = [
    'pending',          # Just created, awaiting payment
    'payment_pending',  # Payment initiated
    'paid',             # Payment confirmed
    'processing',       # Being prepared
    'shipped',          # Dispatched from Japan
    'in_transit',       # Moving internationally
    'out_for_delivery', # Last mile
    'delivered',        # Received
    'cancelled',        # Cancelled
    'refund_requested', # Refund pending
    'refunded',         # Refund completed
]

STATUS_LABELS = {
    'pending': 'Order Placed',
    'payment_pending': 'Awaiting Payment',
    'paid': 'Payment Confirmed',
    'processing': 'Preparing Your Order',
    'shipped': 'Shipped from Japan',
    'in_transit': 'In Transit',
    'out_for_delivery': 'Out for Delivery',
    'delivered': 'Delivered',
    'cancelled': 'Cancelled',
    'refund_requested': 'Refund Requested',
    'refunded': 'Refunded',
}


class Order(Document):
    """
    Full order document supporting international commerce.
    """
    order_number = StringField(max_length=50, required=True, unique=True)
    user_id = StringField(required=True)

    status = StringField(
        max_length=30,
        choices=ORDER_STATUSES,
        default='pending'
    )

    # Items
    items = ListField(EmbeddedDocumentField(OrderItem))

    # Pricing (in customer's currency)
    subtotal = DecimalField(precision=2)
    shipping_fee = DecimalField(precision=2, default=0)
    tax_total = DecimalField(precision=2, default=0)
    discount_amount = DecimalField(precision=2, default=0)
    grand_total = DecimalField(precision=2, required=True)
    currency = StringField(max_length=3, default='JPY')

    # Coupon/promo
    coupon_code = StringField(max_length=50)

    # Addresses and payment
    shipping_address = EmbeddedDocumentField(ShippingAddress, required=True)
    payment = EmbeddedDocumentField(PaymentInfo)
    shipping = EmbeddedDocumentField(ShippingInfo, default=ShippingInfo)

    # History
    status_history = ListField(EmbeddedDocumentField(StatusHistory))

    # Notes
    customer_notes = StringField(max_length=2000)
    admin_notes = StringField(max_length=2000)

    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'orders',
        'indexes': [
            {'fields': ['order_number'], 'unique': True},
            {'fields': ['user_id']},
            {'fields': ['status']},
            {'fields': ['-created_at']},
            {'fields': ['payment.transaction_id']},
        ],
        'ordering': ['-created_at'],
    }

    @staticmethod
    def generate_order_number() -> str:
        prefix = getattr(settings, 'ORDER_NUMBER_PREFIX', 'JP')
        suffix = ''.join(random.choices(string.digits, k=8))
        return f'{prefix}-{suffix}'

    def update_status(self, new_status: str, note: str = '', actor: str = 'system') -> None:
        """Append status change to history and update current status."""
        self.status = new_status
        self.status_history.append(StatusHistory(
            status=new_status,
            label=STATUS_LABELS.get(new_status, new_status),
            note=note,
            actor=actor,
            timestamp=datetime.utcnow()
        ))

    def calculate_totals(self) -> None:
        """Recalculate order totals from items."""
        self.subtotal = sum(float(item.subtotal) for item in self.items)
        self.grand_total = (
            float(self.subtotal)
            + float(self.shipping_fee or 0)
            + float(self.tax_total or 0)
            - float(self.discount_amount or 0)
        )

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Order {self.order_number} ({self.status})'