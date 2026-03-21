"""
Order API views — create, list, detail, tracking, admin management.
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from config.exceptions import success_response, error_response
from .models import Order
from .serializers import OrderSerializer, OrderCreateSerializer
from .services import create_order_from_cart, cancel_order, ship_order
from apps.cart.services import clear_cart
from config.pagination import StandardPagination

logger = logging.getLogger(__name__)


def ok(data=None, message: str = '', status_code: int = status.HTTP_200_OK):
    return success_response(data=data, message=message, status_code=status_code)


def err(message: str, status_code: int = status.HTTP_400_BAD_REQUEST, error: str | None = None):
    return error_response(
        error=error or 'Bad Request' if status_code == status.HTTP_400_BAD_REQUEST else 'Error',
        message=message,
        status_code=status_code,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    POST /api/orders/
    Creates order from active cart.
    """
    serializer = OrderCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid order data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    user_id = str(request.user.id)
    data = serializer.validated_data

    # Get enriched cart items — list of {product_id, quantity} dicts
    from apps.cart.services import get_enriched_cart
    enriched = get_enriched_cart(request)
    cart_items = [
        {'product_id': item['product_id'], 'quantity': item['quantity']}
        for item in enriched['items']
    ]
    if not cart_items:
        return err('Your cart is empty.', status_code=status.HTTP_400_BAD_REQUEST)

    try:
        order = create_order_from_cart(
            user_id=user_id,
            cart_items=cart_items,
            shipping_address_data=data['shipping_address'],
            payment_method=data['payment_method'],
            shipping_service=data.get('shipping_service', 'standard'),
            coupon_code=data.get('coupon_code'),
            notes=data.get('customer_notes'),
            currency=data.get('currency', 'USD'),
        )
    except ValueError as e:
        return err(str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f'Order creation failed for user {user_id}: {e}')
        return err(
            'Order creation failed. Please try again.',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error='Internal Server Error',
        )

    # Clear cart after successful order creation
    clear_cart(request)

    return ok(OrderSerializer(order).data, message='Order created successfully.', status_code=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_orders(request):
    """GET /api/orders/ — current user's orders"""
    user_id = str(request.user.id)
    qs = Order.objects(user_id=user_id).order_by('-created_at')

    # Optional status filter
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(qs), request)
    return paginator.get_paginated_response(OrderSerializer(page, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    """GET /api/orders/<id>/"""
    user_id = str(request.user.id)
    order = Order.objects(id=order_id).first()

    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    # Users can only see their own orders (admins see all)
    if not request.user.is_staff and order.user_id != user_id:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    return ok(OrderSerializer(order).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_by_number(request, order_number):
    """GET /api/orders/number/<order_number>/"""
    user_id = str(request.user.id)
    
    # Try exact match first
    order = Order.objects(order_number=order_number).first()
    
    # If not found and order_number doesn't start with "JP-", try with "JP-" prefix
    if not order and not order_number.startswith('JP-'):
        order = Order.objects(order_number=f'JP-{order_number}').first()
    
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    if not request.user.is_staff and order.user_id != user_id:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    return ok(OrderSerializer(order).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order_view(request, order_id):
    """POST /api/orders/<id>/cancel/"""
    user_id = str(request.user.id)
    order = Order.objects(id=order_id).first()

    if not order or order.user_id != user_id:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    if order.status not in ('pending', 'payment_pending'):
        return err(f'Cannot cancel order in status: {order.status}', status_code=status.HTTP_400_BAD_REQUEST)

    try:
        order = cancel_order(order, reason=request.data.get('reason', ''), actor=user_id)
    except ValueError as e:
        return err(str(e))

    return ok(OrderSerializer(order).data, message='Order cancelled.')


# ─────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_order_list(request):
    """GET /api/orders/admin/ (Admin)"""
    qs = Order.objects.all().order_by('-created_at')

    if status_filter := request.query_params.get('status'):
        qs = qs.filter(status=status_filter)

    if user_id := request.query_params.get('user_id'):
        qs = qs.filter(user_id=user_id)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(qs), request)
    return paginator.get_paginated_response(OrderSerializer(page, many=True).data)


@api_view(['PUT'])
@permission_classes([IsAdminUser])
def admin_update_status(request, order_id):
    """PUT /api/orders/<id>/status/ (Admin)"""
    order = Order.objects(id=order_id).first()
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    new_status = request.data.get('status')
    note = request.data.get('note', '')

    from .models import ORDER_STATUSES
    if new_status not in ORDER_STATUSES:
        return err(
            f'Invalid status. Choose from: {ORDER_STATUSES}',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error='ValidationError',
        )

    order.update_status(new_status, note=note, actor=str(request.user.id))
    order.save()
    return ok(OrderSerializer(order).data, message='Status updated.')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_ship_order(request, order_id):
    """POST /api/orders/<id>/ship/ (Admin)"""
    order = Order.objects(id=order_id).first()
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    carrier = request.data.get('carrier')
    tracking_number = request.data.get('tracking_number')
    if not carrier or not tracking_number:
        return err(
            'carrier and tracking_number are required.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error='ValidationError',
        )

    try:
        order = ship_order(
            order=order,
            carrier=carrier,
            tracking_number=tracking_number,
            tracking_url=request.data.get('tracking_url', ''),
        )
    except ValueError as e:
        return err(str(e))

    return ok(OrderSerializer(order).data, message='Order shipped.')