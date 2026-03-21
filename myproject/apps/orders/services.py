"""
Order lifecycle business logic.
Handles creation, pricing, inventory reservation, and status transitions.
"""
import logging
from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta
from .models import (
    Order, OrderItem, ShippingAddress, PaymentInfo, ShippingInfo, StatusHistory
)
from apps.inventory.models import Inventory
from apps.products.models import Product

logger = logging.getLogger(__name__)

# Shipping rate table (USD) — extend as needed
SHIPPING_RATES = {
    'economy':  {'cost': Decimal('8.99'),  'days': (14, 21)},
    'standard': {'cost': Decimal('12.99'), 'days': (7, 14)},
    'express':  {'cost': Decimal('3.99'),  'days': (3, 5)},
}

FREE_SHIPPING_THRESHOLD = Decimal('80.00')


def calculate_shipping(subtotal: Decimal, service: str = 'standard') -> dict:
    rate = SHIPPING_RATES.get(service, SHIPPING_RATES['standard'])
    fee = Decimal('0.00') if subtotal >= FREE_SHIPPING_THRESHOLD else rate['cost']
    min_days, max_days = rate['days']
    estimated = datetime.utcnow() + timedelta(days=max_days)
    return {
        'fee': fee,
        'service': service,
        'estimated_delivery': estimated,
        'is_free': subtotal >= FREE_SHIPPING_THRESHOLD,
    }


def create_order_from_cart(
    user_id: str,
    cart_items: list,
    shipping_address_data: dict,
    payment_method: str,
    shipping_service: str = 'standard',
    coupon_code: Optional[str] = None,
    notes: Optional[str] = None,
    currency: str = 'USD',
) -> Order:
    """
    Main order creation function.
    1. Validates inventory
    2. Calculates pricing
    3. Reserves inventory
    4. Creates Order document
    """
    if not cart_items:
        raise ValueError('Cart is empty.')

    order_items = []
    subtotal = Decimal('0.00')

    # Validate and reserve inventory for each item
    reserved = []
    try:
        for item in cart_items:
            product = Product.objects(id=item['product_id'], is_active=True).first()
            if not product:
                raise ValueError(f"Product {item['product_id']} not found.")

            qty = int(item['quantity'])
            if qty < 1:
                raise ValueError(f"Invalid quantity for {product.name}.")

            # Check and reserve inventory
            inventory = Inventory.objects(product_id=str(product.id)).first()
            if inventory and inventory.is_tracked:
                if not inventory.can_fulfill(qty):
                    raise ValueError(
                        f'Insufficient stock for {product.name}. '
                        f'Available: {inventory.quantity_available}'
                    )
                inventory.reserve(qty)
                reserved.append((inventory, qty))

            unit_price = Decimal(str(product.pricing.get_effective_price()))
            item_subtotal = unit_price * qty
            subtotal += item_subtotal

            desc = product.description
            order_items.append(OrderItem(
                product_id=str(product.id),
                sku=product.sku,
                name=product.name,
                name_ja=desc.ja if desc else '',
                thumbnail=product.media.thumbnail if product.media else '',
                unit_price=unit_price,
                quantity=qty,
                subtotal=item_subtotal,
                currency=currency,
            ))

    except Exception as e:
        # Roll back any reservations on error
        for inv, qty in reserved:
            inv.release_reservation(qty)
        raise

    # Calculate shipping and tax
    shipping_info = calculate_shipping(subtotal, shipping_service)
    shipping_fee = shipping_info['fee']
    tax_total = Decimal('0.00')   # Adjust per destination country
    discount = Decimal('0.00')   # Apply coupon logic here
    grand_total = subtotal + shipping_fee + tax_total - discount

    # Build shipping address
    addr = ShippingAddress(**{
        k: v for k, v in shipping_address_data.items()
        if k in ['recipient_name', 'postal_code', 'city', 'street', 'building', 'country', 'country_code', 'phone']
    })

    # Create order
    order = Order(
        user_id=str(user_id),
        items=order_items,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        tax_total=tax_total,
        discount_amount=discount,
        grand_total=grand_total,
        currency=currency,
        shipping_address=addr,
        payment=PaymentInfo(
            method=payment_method,
            status='pending',
            amount=grand_total,
            currency=currency,
        ),
        shipping=ShippingInfo(
            service=shipping_service,
            estimated_delivery=shipping_info['estimated_delivery'],
            shipping_cost=shipping_fee,
        ),
        coupon_code=coupon_code,
        customer_notes=notes,
        status_history=[StatusHistory(
            status='pending',
            label='Order Placed',
            note='Order created. Awaiting payment.',
            timestamp=datetime.utcnow()
        )]
    )
    order.save()

    logger.info(f'Created order {order.order_number} for user {user_id}, total={grand_total} {currency}')
    return order


def confirm_payment(order: Order, transaction_id: str, provider: str = 'manual') -> Order:
    """Called when payment webhook confirms success."""
    order.payment.status = 'paid'
    order.payment.transaction_id = transaction_id
    order.payment.provider = provider
    order.payment.paid_at = datetime.utcnow()
    order.update_status('paid', note=f'Payment confirmed via {provider}. TX: {transaction_id}')

    # Confirm inventory reservations
    for item in order.items:
        inventory = Inventory.objects(product_id=item.product_id).first()
        if inventory:
            inventory.confirm_sale(item.quantity)

    order.save()
    return order


def cancel_order(order: Order, reason: str = '', actor: str = 'system') -> Order:
    """Cancel order and release inventory."""
    if order.status in ('delivered', 'shipped', 'refunded'):
        raise ValueError(f'Cannot cancel order in status: {order.status}')

    for item in order.items:
        inventory = Inventory.objects(product_id=item.product_id).first()
        if inventory:
            inventory.release_reservation(item.quantity)

    order.update_status('cancelled', note=reason or 'Order cancelled.', actor=actor)
    order.save()
    return order


def ship_order(
    order: Order,
    carrier: str,
    tracking_number: str,
    tracking_url: str = '',
    estimated_delivery: Optional[datetime] = None,
) -> Order:
    """Mark order as shipped with tracking info."""
    if order.status not in ('paid', 'processing'):
        raise ValueError(f'Order must be paid/processing to ship. Current: {order.status}')

    order.shipping.carrier = carrier
    order.shipping.tracking_number = tracking_number
    order.shipping.tracking_url = tracking_url
    order.shipping.shipped_at = datetime.utcnow()
    if estimated_delivery:
        order.shipping.estimated_delivery = estimated_delivery

    order.update_status('shipped', note=f'Shipped via {carrier}. Tracking: {tracking_number}')
    order.save()
    return order