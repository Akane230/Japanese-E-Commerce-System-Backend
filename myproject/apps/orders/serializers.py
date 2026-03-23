from rest_framework import serializers
from .models import Order, OrderItem, ShippingAddress, PaymentInfo


class ShippingAddressSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=200)
    postal_code = serializers.CharField(max_length=20)
    city = serializers.CharField(max_length=100)
    street = serializers.CharField(max_length=500)
    building = serializers.CharField(max_length=200, allow_blank=True, required=False)
    country = serializers.CharField(max_length=100)
    country_code = serializers.CharField(max_length=3, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)


class OrderItemSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    name = serializers.CharField()
    name_ja = serializers.CharField(allow_blank=True, required=False)
    thumbnail = serializers.CharField(allow_blank=True, required=False)
    sku = serializers.CharField(allow_blank=True, required=False)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)


class PaymentInfoSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=['gcash', 'bank_transfer', 'cod', 'maya', 'instapay', 'other']
    )
    status = serializers.CharField(read_only=True)
    transaction_id = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    proof_url = serializers.CharField(allow_blank=True, required=False, allow_null=True)
    submitted_at = serializers.DateTimeField(read_only=True, allow_null=True)
    confirmed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    currency = serializers.CharField(max_length=3, read_only=True)
    paid_at = serializers.DateTimeField(read_only=True, allow_null=True)
    refund_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    refunded_at = serializers.DateTimeField(read_only=True, allow_null=True)
    failure_reason = serializers.CharField(read_only=True, allow_null=True, allow_blank=True)


class OrderCreateSerializer(serializers.Serializer):
    """Used when customer places an order."""
    shipping_address = ShippingAddressSerializer()
    payment_method = serializers.ChoiceField(
        choices=['gcash', 'bank_transfer', 'cod', 'maya', 'instapay', 'other']
    )
    shipping_service = serializers.ChoiceField(
        choices=['economy', 'standard', 'express'],
        default='standard'
    )
    shipping_fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    coupon_code = serializers.CharField(max_length=50, allow_blank=True, required=False)
    customer_notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    currency = serializers.CharField(max_length=3, default='JPY')


class StatusHistorySerializer(serializers.Serializer):
    status = serializers.CharField()
    label = serializers.CharField()
    note = serializers.CharField(allow_blank=True)
    timestamp = serializers.DateTimeField()


class ShippingInfoSerializer(serializers.Serializer):
    carrier = serializers.CharField(allow_blank=True, allow_null=True)
    service = serializers.CharField(allow_blank=True, allow_null=True)
    tracking_number = serializers.CharField(allow_blank=True, allow_null=True)
    tracking_url = serializers.CharField(allow_blank=True, allow_null=True)
    estimated_delivery = serializers.DateTimeField(allow_null=True)
    shipped_at = serializers.DateTimeField(allow_null=True)
    delivered_at = serializers.DateTimeField(allow_null=True)


class OrderSerializer(serializers.Serializer):
    """Full order response serializer."""
    id = serializers.SerializerMethodField()
    order_number = serializers.CharField()
    user_id = serializers.CharField()
    status = serializers.CharField()
    items = OrderItemSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    shipping_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    grand_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    shipping_address = ShippingAddressSerializer()
    payment = PaymentInfoSerializer(allow_null=True)
    shipping = ShippingInfoSerializer(allow_null=True)
    status_history = StatusHistorySerializer(many=True)
    customer_notes = serializers.CharField(allow_blank=True, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_id(self, obj):
        return str(obj.id)