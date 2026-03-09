# apps/cart/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .services import (
    get_enriched_cart, add_to_cart, update_cart_item,
    remove_from_cart, clear_cart
)
from apps.inventory.models import Inventory



def ok(data=None, message='', status_code=200):
    return Response({'success': True, 'message': message, 'data': data or {}}, status=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
def cart_view(request):
    """GET /api/cart/ - Works for both guest and authenticated users."""
    return ok(get_enriched_cart(request))


@api_view(['POST'])
@permission_classes([AllowAny])
def cart_add(request):
    """POST /api/cart/add/ — {product_id, quantity}"""
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity', 1))

    if not product_id:
        return Response({'success': False, 'message': 'product_id required.'}, status=400)
    if quantity < 1:
        return Response({'success': False, 'message': 'quantity must be >= 1.'}, status=400)

    # Check inventory
    inv = Inventory.objects(product_id=str(product_id)).first()
    if inv and inv.is_tracked and not inv.can_fulfill(quantity):
        return Response({'success': False, 'message': f'Only {inv.quantity_available} in stock.'}, status=400)

    add_to_cart(request, product_id, quantity)
    return ok(get_enriched_cart(request), 'Added to cart.', 201)


@api_view(['PUT'])
@permission_classes([AllowAny])
def cart_update(request):
    """PUT /api/cart/update/ — {product_id, quantity}"""
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity', 0))

    if not product_id:
        return Response({'success': False, 'message': 'product_id required.'}, status=400)

    update_cart_item(request, product_id, quantity)
    return ok(get_enriched_cart(request), 'Cart updated.')


@api_view(['DELETE'])
@permission_classes([AllowAny])
def cart_remove(request):
    """DELETE /api/cart/remove/ — {product_id}"""
    product_id = request.data.get('product_id')
    if not product_id:
        return Response({'success': False, 'message': 'product_id required.'}, status=400)

    update_cart_item(request, product_id, 0)  # Set quantity to 0 to remove
    return ok(get_enriched_cart(request), 'Item removed.')


@api_view(['DELETE'])
@permission_classes([AllowAny])
def cart_clear(request):
    """DELETE /api/cart/clear/"""
    clear_cart(request)
    return ok({}, 'Cart cleared.')