import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from config.exceptions import success_response, error_response
from apps.products.models import Product
from config.pagination import StandardPagination
from .models import Inventory

logger = logging.getLogger(__name__)


def ok(data=None, message: str = '', status_code: int = status.HTTP_200_OK):
    return success_response(data=data, message=message, status_code=status_code)


def _serialize(inv: Inventory) -> dict:
    return {
        'id': str(inv.id),
        'product_id': inv.product_id, 
        'quantity_available': inv.quantity_available,
        'quantity_reserved': inv.quantity_reserved,
        'quantity_sold': inv.quantity_sold,
        'quantity_on_hand': inv.quantity_on_hand,
        'is_in_stock': inv.is_in_stock,
        'is_low_stock': inv.is_low_stock,
        'reorder_threshold': inv.reorder_threshold,
        'reorder_quantity': inv.reorder_quantity,
        'is_tracked': inv.is_tracked,
        'allow_backorder': inv.allow_backorder,
        'last_restocked_at': inv.last_restocked_at.isoformat() if inv.last_restocked_at else None,
        'updated_at': inv.updated_at.isoformat(),
    }

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_inventory_list(request):
    """GET /api/inventory/ (Admin)"""
    inv = Inventory.objects.all().order_by('product_id')
    
    # Filter out inventory items where product doesn't exist or is inactive
    filtered_inv = []
    for item in inv:
        product = Product.objects(id=item.product_id, is_active=True).first()
        if product:  # Only include if product exists and is active
            filtered_inv.append(item)
    
    paginator = StandardPagination()
    page = paginator.paginate_queryset(filtered_inv, request)
    
    result = []
    for item in page:
        product = Product.objects(id=item.product_id).first()
        result.append({
            **_serialize(item),
            'product_name': product.name if product else None, 
            'product_slug': product.slug if product else None,
        })
    
    # Filter out any results with None product_name (deleted products)
    result = [r for r in result if r['product_name'] is not None]
    
    return paginator.get_paginated_response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_check(request, product_id):
    """GET /api/inventory/<product_id>/stock/ — public stock info"""
    inv = Inventory.objects(product_id=product_id).first()
    if not inv:
        return ok({'in_stock': True, 'quantity_available': 0, 'is_tracked': False})
    return ok({
        'in_stock': inv.is_in_stock,
        'quantity_available': inv.quantity_available,
        'is_low_stock': inv.is_low_stock,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_inventory_detail(request, product_id):
    """GET /api/inventory/<product_id>/ (Admin)"""
    inv = Inventory.objects(product_id=product_id).first()
    if not inv:
        return error_response(
            error='NotFound',
            message='Inventory not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return ok(_serialize(inv))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_restock(request, product_id):
    """POST /api/inventory/<product_id>/restock/ (Admin) — {quantity}"""
    inv = Inventory.objects(product_id=product_id).first()
    if not inv:
        return error_response(
            error='NotFound',
            message='Inventory not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    quantity = request.data.get('quantity')
    if not quantity or int(quantity) <= 0:
        return error_response(
            error='ValidationError',
            message='quantity must be > 0.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    inv.restock(int(quantity))
    logger.info(f'Restocked product {product_id} by {quantity} units.')
    return ok(_serialize(inv), message=f'Restocked {quantity} units.')


@api_view(['PUT'])
@permission_classes([IsAdminUser])
def admin_update_inventory(request, product_id):
    """PUT /api/inventory/<product_id>/ (Admin)"""
    inv = Inventory.objects(product_id=product_id).first()
    if not inv:
        return error_response(
            error='NotFound',
            message='Inventory not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    allowed_fields = [
        'quantity_available', 'reorder_threshold', 'reorder_quantity',
        'is_tracked', 'allow_backorder'
    ]
    for field in allowed_fields:
        if field in request.data:
            setattr(inv, field, request.data[field])

    inv.save()
    return ok(_serialize(inv), message='Inventory updated.')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_low_stock_list(request):
    """GET /api/inventory/low-stock/ (Admin)"""
    
    low_stock = [
        inv for inv in Inventory.objects(is_tracked=True)
        if inv.is_low_stock
    ]

    result = []
    for inv in low_stock:
        product = Product.objects(id=inv.product_id, is_active=True).first()
        if product:  # Only include if product exists
            result.append({
                **_serialize(inv),
                'product_name': product.name,
                'product_slug': product.slug,
            })

    paginator = StandardPagination()
    page = paginator.paginate_queryset(result, request)
    return paginator.get_paginated_response(page)