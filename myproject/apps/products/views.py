"""
Product API views — public browsing, search, admin CRUD.
"""
import logging
import json
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import Product
from .serializers import ProductListSerializer, ProductDetailSerializer, ProductCreateSerializer
from .services import get_product_queryset, generate_unique_slug, get_product_with_inventory
from config.pagination import StandardPagination
from config.permissions import IsAdminOrReadOnly
from config.exceptions import success_response, error_response

logger = logging.getLogger(__name__)


def parse_form_data(data):
    """
    Convert a Django QueryDict (multipart FormData) into a plain Python dict,
    unwrapping single-value lists and JSON-decoding any fields that the
    frontend serialised with JSON.stringify().
    """
    parsed = dict(data)  # {key: [val, ...]} for every key

    json_fields = ['pricing', 'description', 'attributes', 'shipping']

    for field in json_fields:
        if field in parsed:
            val = parsed[field]
            if isinstance(val, list):
                val = val[0] if val else ''
            if isinstance(val, str):
                if val.strip() and val != 'null':
                    try:
                        parsed[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
                else:
                    del parsed[field]

    # Unwrap remaining single-value list fields (QueryDict artefact)
    for key in list(parsed.keys()):
        if isinstance(parsed[key], list) and len(parsed[key]) == 1:
            parsed[key] = parsed[key][0]

    return parsed


def _pop_bool_flag(d, key):
    """Safely pop a boolean flag from a plain dict."""
    val = d.pop(key, False)
    if isinstance(val, list):
        val = val[0] if val else False
    if isinstance(val, str):
        return val.lower() in ('true', '1', 'yes')
    return bool(val)


def ok(data, message: str = '', status_code: int = status.HTTP_200_OK):
    return success_response(data=data, message=message, status_code=status_code)


# ─────────────────────────────────────────────
# Public views
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def product_list(request):
    """
    GET /api/products/
    Query params: category_id, category_slug, min_price, max_price, search,
                  sort_by, is_featured, tag, page, page_size
    """
    category_id = request.query_params.get('category_id')
    category_slug = request.query_params.get('category_slug')  # Add support for slug
    min_price   = request.query_params.get('min_price')
    max_price   = request.query_params.get('max_price')
    search      = request.query_params.get('search', '').strip()
    sort_by     = request.query_params.get('sort_by', 'newest')
    is_featured = request.query_params.get('is_featured', '').lower() == 'true'
    tag         = request.query_params.get('tag')

    qs = get_product_queryset(
        category_id=category_id,
        category_slug=category_slug,
        min_price=float(min_price) if min_price else None,
        max_price=float(max_price) if max_price else None,
        search=search or None,
        sort_by=sort_by,
        is_featured=is_featured or None,
        tag=tag,
    )

    paginator = StandardPagination()
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(ProductListSerializer(page, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_featured(request):
    """GET /api/products/featured/"""
    qs = get_product_queryset(is_featured=True, sort_by='-created_at')
    return ok(ProductListSerializer(list(qs[:12]), many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_search(request):
    """GET /api/products/search/?q=matcha"""
    query = request.query_params.get('q', '').strip()
    if not query:
        return error_response(
            error='ValidationError',
            message='Search query required.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    qs = get_product_queryset(search=query, sort_by='rating')
    paginator = StandardPagination()
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(ProductListSerializer(page, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail(request, slug):
    """GET /api/products/<slug>/"""
    result = get_product_with_inventory(slug)
    if not result:
        return error_response(
            error='NotFound',
            message='Product not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )
    product_data = ProductDetailSerializer(result['product']).data
    product_data['in_stock']           = result['in_stock']
    product_data['quantity_available'] = result['quantity_available']
    product_data['is_low_stock']       = result['is_low_stock']
    return ok(product_data)


# ─────────────────────────────────────────────
# Admin CRUD
# ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAdminUser])
def product_create(request):
    """POST /api/products/admin/create/"""
    from apps.inventory.models import Inventory

    # 1. Grab files FIRST — before request.data is touched
    thumbnail_file = request.FILES.get('thumbnail_file')
    image_files    = request.FILES.getlist('image_files')
    video_file     = request.FILES.get('video_file')

    # 2. QueryDict → plain dict, JSON fields decoded
    data = parse_form_data(request.data)

    # 3. Strip file keys — DRF FileField would choke on the string filename
    for key in ('thumbnail_file', 'image_files', 'video_file'):
        data.pop(key, None)

    # 4. Pop flags that don't belong in the serializer
    _pop_bool_flag(data, 'remove_thumbnail')
    _pop_bool_flag(data, 'remove_video')

    # 5. Normalise category_ids (multi-value FormData field)
    raw_cats = request.data.getlist('category_ids') if hasattr(request.data, 'getlist') else request.data.get('category_ids', [])
    if isinstance(raw_cats, str):
        raw_cats = [c.strip() for c in raw_cats.split(',') if c.strip()]
    data['category_ids'] = [c for c in raw_cats if c]

    # 6. Validate
    serializer = ProductCreateSerializer(data=data)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid product data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    validated = serializer.validated_data
    if not validated.get('slug'):
        from .services import generate_unique_slug
        validated['slug'] = generate_unique_slug(validated['name'])

    product = _build_product_from_data(validated)

    # 7. Upload to Cloudinary
    try:
        if thumbnail_file:
            product.media.upload_thumbnail(thumbnail_file)
        if image_files:
            product.media.upload_images(image_files)
        if video_file:
            product.media.upload_video(video_file)
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        return error_response(
            error='MediaUploadError',
            message=f'File upload failed: {str(e)}',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 8. Reassign media so MongoEngine marks the field dirty and writes it to Mongo.
    #    In-place mutations on an EmbeddedDocument are NOT tracked automatically.
    from .models import ProductMedia
    product.media = ProductMedia(
        thumbnail=product.media.thumbnail,
        images=list(product.media.images or []),
        video_url=product.media.video_url,
    )

    product.save()
    Inventory(product_id=str(product.id), quantity_available=0).save()
    return ok(ProductDetailSerializer(product).data, status_code=201)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def product_update(request, slug):
    """PUT/PATCH /api/products/<slug>/admin/"""
    product = Product.objects(slug=slug).first()
    if not product:
        return error_response(
            error='NotFound',
            message='Product not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 1. Grab files FIRST
    thumbnail_file = request.FILES.get('thumbnail_file')
    image_files    = request.FILES.getlist('image_files')
    video_file     = request.FILES.get('video_file')

    # 2. QueryDict → plain dict, JSON fields decoded
    data = parse_form_data(request.data)

    # 3. Strip file keys
    for key in ('thumbnail_file', 'image_files', 'video_file'):
        data.pop(key, None)

    # 4. Pop boolean flags
    remove_thumbnail_flag = _pop_bool_flag(data, 'remove_thumbnail')
    remove_video_flag     = _pop_bool_flag(data, 'remove_video')
    remove_images_flag    = data.pop('remove_images', [])
    if isinstance(remove_images_flag, str):
        try:
            remove_images_flag = json.loads(remove_images_flag)
        except (json.JSONDecodeError, TypeError):
            remove_images_flag = []
    if not isinstance(remove_images_flag, list):
        remove_images_flag = []

    # 5. Normalise category_ids
    raw_cats = request.data.getlist('category_ids') if hasattr(request.data, 'getlist') else request.data.get('category_ids', [])
    if isinstance(raw_cats, str):
        raw_cats = [c.strip() for c in raw_cats.split(',') if c.strip()]
    data['category_ids'] = [c for c in raw_cats if c]

    # 6. Validate
    serializer = ProductCreateSerializer(instance=product, data=data, partial=True)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid product data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    validated = serializer.validated_data

    # 7. Scalar fields
    for field, value in validated.items():
        if field not in ('thumbnail_file', 'image_files', 'video_file',
                         'description', 'pricing', 'attributes', 'shipping'):
            setattr(product, field, value)

    # 8. Embedded documents — always reassign, never mutate in place
    from .models import (
        BilingualText, ProductPricing, ProductAttributes,
        ProductShipping, StorageInstructions,
    )

    if validated.get('description'):
        d = validated['description']
        product.description = BilingualText(en=d.get('en', ''), ja=d.get('ja', ''))

    if validated.get('pricing'):
        p = validated['pricing']
        product.pricing = ProductPricing(
            base_price=p.get('base_price', 0),
            sale_price=p.get('sale_price'),
            currency=p.get('currency', 'JPY'),
            tax_rate=p.get('tax_rate', 0.10),
            tax_included=p.get('tax_included', True),
        )

    if validated.get('attributes'):
        a = validated['attributes']
        si = a.get('storage_instructions', {})
        product.attributes = ProductAttributes(
            weight_grams=a.get('weight_grams'),
            brand=a.get('brand', ''),
            certifications=a.get('certifications', []),
            ingredients=a.get('ingredients', []),
            allergens=a.get('allergens', []),
            shelf_life_days=a.get('shelf_life_days'),
            country_of_origin=a.get('country_of_origin', 'Japan'),
            barcode=a.get('barcode', ''),
            net_weight_grams=a.get('net_weight_grams'),
            storage_instructions=StorageInstructions(en=si.get('en', ''), ja=si.get('ja', '')),
        )

    if validated.get('shipping'):
        s = validated['shipping']
        product.shipping = ProductShipping(
            weight_kg=s.get('weight_kg'),
            dimensions_cm=s.get('dimensions_cm'),
            requires_cold_chain=s.get('requires_cold_chain', False),
            ships_internationally=s.get('ships_internationally', True),
            domestic_only=s.get('domestic_only', False),
            prohibited_countries=s.get('prohibited_countries', []),
            handling_days=s.get('handling_days', 2),
        )

   
    from .models import ProductMedia
    scratch = ProductMedia(
        thumbnail=product.media.thumbnail if product.media else None,
        images=list(product.media.images or []) if product.media else [],
        video_url=product.media.video_url if product.media else None,
    )

    try:
        if thumbnail_file:
            if scratch.thumbnail:
                try:
                    scratch.delete_thumbnail()
                except Exception as e:
                    logger.warning(f"Failed to delete old thumbnail: {e}")
            scratch.upload_thumbnail(thumbnail_file)

        if image_files:
            scratch.upload_images(image_files)

        if video_file:
            if scratch.video_url:
                try:
                    scratch.delete_video()
                except Exception as e:
                    logger.warning(f"Failed to delete old video: {e}")
            scratch.upload_video(video_file)

        if remove_thumbnail_flag and scratch.thumbnail:
            try:
                scratch.delete_thumbnail()
            except Exception as e:
                logger.warning(f"Error deleting thumbnail via flag: {e}")
            scratch.thumbnail = None

        if remove_video_flag and scratch.video_url:
            try:
                scratch.delete_video()
            except Exception as e:
                logger.warning(f"Error deleting video via flag: {e}")
            scratch.video_url = None

        if remove_images_flag:
            # Sort indices descending to avoid index shifting
            for idx in sorted(remove_images_flag, reverse=True):
                if 0 <= idx < len(scratch.images):
                    try:
                        public_id = scratch.images[idx]
                        scratch.delete_image(public_id)
                    except Exception as e:
                        logger.warning(f"Error deleting image at index {idx}: {e}")

    except Exception as e:
        logger.error(f"File upload failed during update: {e}")
        return error_response(
            error='MediaUploadError',
            message=f'File upload failed: {str(e)}',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    product.media = scratch  # reassignment marks the field dirty for MongoEngine
    product.save()

    logger.info(f"Product {slug} updated successfully, media.thumbnail={product.media.thumbnail if product.media else None}")

    return ok(ProductDetailSerializer(product).data, message='Product updated.')


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def product_delete(request, slug):
    """DELETE /api/products/<slug>/admin/delete/"""
    product = Product.objects(slug=slug).first()
    if not product:
        return error_response(
            error='NotFound',
            message='Product not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )
    product.delete_all_media()
    product.is_active = False
    product.save()
    return ok({}, message='Product deactivated and media cleaned up.')


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _build_product_from_data(data: dict) -> Product:
    """Build a new Product document from validated serializer data."""
    from .models import (
        BilingualText, ProductMedia, ProductPricing,
        ProductAttributes, ProductShipping, StorageInstructions,
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

    product.media = ProductMedia()

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
