"""
Product API views — public browsing, search, admin CRUD.
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import Product
from .serializers import ProductListSerializer, ProductDetailSerializer, ProductCreateSerializer
from .services import get_product_queryset, generate_unique_slug, get_product_with_inventory
from config.pagination import StandardPagination
from config.permissions import IsAdminOrReadOnly

logger = logging.getLogger(__name__)


def ok(data, message='', status_code=200):
    return Response({'success': True, 'message': message, 'data': data}, status=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_list(request):
    """
    GET /api/products/
    Query params:
      - category_id
      - min_price, max_price
      - search
      - sort_by: newest|oldest|price_asc|price_desc|rating|popular
      - is_featured: true/false
      - tag
      - page, page_size
    """
    category_id = request.query_params.get('category_id')
    min_price = request.query_params.get('min_price')
    max_price = request.query_params.get('max_price')
    search = request.query_params.get('search', '').strip()
    sort_by = request.query_params.get('sort_by', 'newest')
    is_featured = request.query_params.get('is_featured', '').lower() == 'true'
    tag = request.query_params.get('tag')

    qs = get_product_queryset(
        category_id=category_id,
        min_price=float(min_price) if min_price else None,
        max_price=float(max_price) if max_price else None,
        search=search or None,
        sort_by=sort_by,
        is_featured=is_featured or None,
        tag=tag,
    )

    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(qs), request)
    serializer = ProductListSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_featured(request):
    """GET /api/products/featured/"""
    qs = get_product_queryset(is_featured=True, sort_by='-created_at')
    products = list(qs[:12])
    return ok(ProductListSerializer(products, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_search(request):
    """GET /api/products/search/?q=matcha"""
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response({'success': False, 'message': 'Search query required.'}, status=400)

    qs = get_product_queryset(search=query, sort_by='rating')
    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(qs), request)
    return paginator.get_paginated_response(ProductListSerializer(page, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail(request, slug):
    """GET /api/products/<slug>/"""
    result = get_product_with_inventory(slug)
    if not result:
        return Response({'success': False, 'message': 'Product not found.'}, status=404)

    product_data = ProductDetailSerializer(result['product']).data
    product_data['in_stock'] = result['in_stock']
    product_data['quantity_available'] = result['quantity_available']
    product_data['is_low_stock'] = result['is_low_stock']

    return ok(product_data)


# ─────────────────────────────────────────────
# Admin CRUD
# ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAdminUser])
def product_create(request):
    """POST /api/products/ (Admin)"""
    from apps.inventory.models import Inventory

    serializer = ProductCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors}, status=400)

    data = serializer.validated_data
    if not data.get('slug'):
        data['slug'] = generate_unique_slug(data['name'])

    # Build MongoEngine embedded docs
    product = _build_product_from_data(data)
    product.save()

    # Auto-create inventory record
    Inventory(product_id=str(product.id), quantity_available=0).save()

    return ok(ProductDetailSerializer(product).data, status_code=201)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def product_update(request, slug):
    """PUT /api/products/<slug>/ (Admin)"""
    product = Product.objects(slug=slug).first()
    if not product:
        return Response({'success': False, 'message': 'Product not found.'}, status=404)

    serializer = ProductCreateSerializer(instance=product, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({'success': False, 'errors': serializer.errors}, status=400)

    data = serializer.validated_data
    for field, value in data.items():
        setattr(product, field, value)
    product.save()

    return ok(ProductDetailSerializer(product).data, message='Product updated.')


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def product_delete(request, slug):
    """DELETE /api/products/<slug>/ (Admin)"""
    product = Product.objects(slug=slug).first()
    if not product:
        return Response({'success': False, 'message': 'Product not found.'}, status=404)
    product.is_active = False
    product.save()
    return ok({}, message='Product deactivated.')


def _build_product_from_data(data: dict) -> Product:
    """Helper to build Product document from validated data dict."""
    from .models import (
        BilingualText, ProductMedia, ProductPricing,
        ProductAttributes, ProductShipping, StorageInstructions
    )

    product = Product(
        sku=data['sku'],
        name=data['name'],
        slug=data.get('slug', ''),
        category_ids=data.get('category_ids', []),
        tags=data.get('tags', []),
        is_active=data.get('is_active', True),
        is_featured=data.get('is_featured', False),
    )

    if desc := data.get('description'):
        product.description = BilingualText(en=desc.get('en', ''), ja=desc.get('ja', ''))

    if media := data.get('media'):
        product.media = ProductMedia(
            thumbnail=media.get('thumbnail', ''),
            images=media.get('images', []),
            video_url=media.get('video_url', ''),
        )

    pricing = data['pricing']
    product.pricing = ProductPricing(
        base_price=pricing['base_price'],
        sale_price=pricing.get('sale_price'),
        currency=pricing.get('currency', 'JPY'),
        tax_rate=pricing.get('tax_rate', 0.10),
        tax_included=pricing.get('tax_included', True),
    )

    if attrs := data.get('attributes'):
        si = attrs.get('storage_instructions', {})
        product.attributes = ProductAttributes(
            weight_grams=attrs.get('weight_grams'),
            brand=attrs.get('brand', ''),
            certifications=attrs.get('certifications', []),
            ingredients=attrs.get('ingredients', []),
            allergens=attrs.get('allergens', []),
            shelf_life_days=attrs.get('shelf_life_days'),
            storage_instructions=StorageInstructions(en=si.get('en', ''), ja=si.get('ja', '')),
        )

    if ship := data.get('shipping'):
        product.shipping = ProductShipping(
            weight_kg=ship.get('weight_kg'),
            requires_cold_chain=ship.get('requires_cold_chain', False),
            ships_internationally=ship.get('ships_internationally', True),
            domestic_only=ship.get('domestic_only', False),
            handling_days=ship.get('handling_days', 2),
        )

    return product