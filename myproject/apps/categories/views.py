from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from config.exceptions import success_response, error_response
from .models import Category
from .serializers import CategorySerializer


def ok(data=None, message: str = '', status_code: int = status.HTTP_200_OK):
    return success_response(data=data, message=message, status_code=status_code)


def _build_tree(categories, parent_id=None) -> list:
    """Build nested category tree."""
    result = []
    for cat in categories:
        if cat.parent_id == parent_id or (parent_id is None and not cat.parent_id):
            serialized = CategorySerializer(cat).data
            serialized['children'] = _build_tree(categories, str(cat.id))
            result.append(serialized)
    return sorted(result, key=lambda x: x['display_order'])


@api_view(['GET'])
@permission_classes([AllowAny])
def category_list(request):
    """GET /api/categories/ — flat list or nested tree"""
    nested = request.query_params.get('nested', 'false').lower() == 'true'
    cats = list(Category.objects(is_active=True).order_by('display_order'))

    if nested:
        return ok(_build_tree(cats))

    return ok(CategorySerializer(cats, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def category_detail(request, slug):
    """GET /api/categories/<slug>/"""
    cat = Category.objects(slug=slug, is_active=True).first()
    if not cat:
        return error_response(
            error='NotFound',
            message='Category not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    data = CategorySerializer(cat).data
    children = Category.objects(parent_id=str(cat.id), is_active=True)
    data['children'] = CategorySerializer(list(children), many=True).data
    return ok(data)


@api_view(['PUT'])
@permission_classes([IsAdminUser])
def category_update(request, slug):
    """PUT /api/categories/<slug>/ (Admin)"""
    cat = Category.objects(slug=slug).first()
    if not cat:
        return error_response(
            error='NotFound',
            message='Category not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    from .models import LocalizedName
    
    # Update basic fields
    name_en = request.data.get('name', {}).get('en') or request.data.get('name_en', '').strip()
    name_ja = request.data.get('name', {}).get('ja') or request.data.get('name_ja', '').strip()
    
    if name_en or name_ja:
        cat.name = LocalizedName(
            en=name_en or cat.name.en,
            ja=name_ja or cat.name.ja
        )
    
    # Update description
    if 'description' in request.data:
        desc_en = request.data.get('description', {}).get('en', '')
        desc_ja = request.data.get('description', {}).get('ja', '')
        if desc_en or desc_ja:
            cat.description = LocalizedName(
                en=desc_en or (cat.description.en if cat.description else ''),
                ja=desc_ja or (cat.description.ja if cat.description else '')
            )
    
    # Update other fields
    if 'emoji' in request.data:
        cat.emoji = request.data.get('emoji') or None
    
    if 'image_url' in request.data:
        cat.image_url = request.data.get('image_url') or None
    
    if 'is_active' in request.data:
        cat.is_active = request.data.get('is_active', True)
    
    if 'display_order' in request.data:
        cat.display_order = request.data.get('display_order', 0)
    
    # Handle parent_id changes (update ancestors and depth)
    parent_id = request.data.get('parent_id')
    if parent_id is not None:
        cat.parent_id = parent_id or None
        ancestors = []
        depth = 0
        if parent_id:
            parent = Category.objects(id=parent_id).first()
            if parent:
                ancestors = parent.ancestors + [parent_id]
                depth = parent.depth + 1
        cat.ancestors = ancestors
        cat.depth = depth
    
    cat.save()
    return ok(CategorySerializer(cat).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def category_create(request):
    """POST /api/categories/ (Admin)"""
    from datetime import datetime
    name_en = request.data.get('name_en', '').strip()
    name_ja = request.data.get('name_ja', '').strip()
    slug = request.data.get('slug', '').strip()
    parent_id = request.data.get('parent_id')

    if not name_en or not slug:
        return error_response(
            error='ValidationError',
            message='name_en and slug are required.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if Category.objects(slug=slug).first():
        return error_response(
            error='Conflict',
            message='Slug already in use.',
            status_code=status.HTTP_409_CONFLICT,
        )

    from .models import LocalizedName
    ancestors = []
    depth = 0
    if parent_id:
        parent = Category.objects(id=parent_id).first()
        if parent:
            ancestors = parent.ancestors + [parent_id]
            depth = parent.depth + 1

    cat = Category(
        name=LocalizedName(en=name_en, ja=name_ja),
        slug=slug,
        emoji=request.data.get('emoji') or None,
        description=LocalizedName(
            en=request.data.get('description_en') or '',
            ja=request.data.get('description_ja') or ''
        ) if (request.data.get('description_en') or request.data.get('description_ja')) else None,
        parent_id=parent_id,
        ancestors=ancestors,
        depth=depth,
        image_url=request.data.get('image_url') or None,
        display_order=request.data.get('display_order', 0),
        is_active=request.data.get('is_active', True),
    )
    cat.save()
    return ok(CategorySerializer(cat).data, status_code=201)