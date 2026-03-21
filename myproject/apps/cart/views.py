# apps/cart/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from config.exceptions import success_response, error_response
from .services import (
    get_enriched_cart,
    add_to_cart,
    update_cart_item,
    remove_from_cart,
    clear_cart,
)
from apps.inventory.models import Inventory
from bson import ObjectId
from mongoengine.errors import ValidationError



def ok(data=None, message: str = '', status_code: int = status.HTTP_200_OK):
    return success_response(data=data, message=message, status_code=status_code)


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
        return error_response(
            error='ValidationError',
            message='product_id required.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    
    # Validate ObjectId format
    if not ObjectId.is_valid(str(product_id)):
        return error_response(
            error='ValidationError',
            message='Invalid product ID format.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    
    if quantity < 1:
        return error_response(
            error='ValidationError',
            message='quantity must be >= 1.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Check if product exists
    from apps.products.models import Product
    product = Product.objects(id=str(product_id), is_active=True).first()
    if not product:
        return error_response(
            error='NotFound',
            message='Product not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Check inventory
    inv = Inventory.objects(product_id=str(product_id)).first()
    if inv and inv.is_tracked and not inv.can_fulfill(quantity):
        return error_response(
            error='ValidationError',
            message=f'Only {inv.quantity_available} in stock.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    add_to_cart(request, product_id, quantity)
    return ok(get_enriched_cart(request), 'Added to cart.', 201)


@api_view(['PUT'])
@permission_classes([AllowAny])
def cart_update(request):
    """PUT /api/cart/update/ — {product_id, quantity}"""
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity', 0))

    if not product_id:
        return error_response(
            error='ValidationError',
            message='product_id required.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    
    # Validate ObjectId format
    if not ObjectId.is_valid(str(product_id)):
        return error_response(
            error='ValidationError',
            message='Invalid product ID format.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    update_cart_item(request, product_id, quantity)
    return ok(get_enriched_cart(request), 'Cart updated.')


@api_view(['DELETE'])
@permission_classes([AllowAny])
def cart_remove(request):
    """DELETE /api/cart/remove/ — {product_id}"""
    product_id = request.data.get('product_id')

    if not product_id:
        return error_response(
            error='ValidationError',
            message='product_id required.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    
    # Validate ObjectId format
    if not ObjectId.is_valid(str(product_id)):
        return error_response(
            error='ValidationError',
            message='Invalid product ID format.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    remove_from_cart(request, product_id)
    return ok(get_enriched_cart(request), 'Removed from cart.')


@api_view(['DELETE'])
@permission_classes([AllowAny])
def cart_clear(request):
    """DELETE /api/cart/clear/"""
    clear_cart(request)
    return ok({}, 'Cart cleared.')