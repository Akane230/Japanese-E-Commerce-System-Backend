from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import serializers
from .models import Category
from .serializers import CategorySerializer


def ok(data=None, message='', status_code=200):
    return Response({'success': True, 'message': message, 'data': data or {}}, status=status_code)


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
        return Response({'success': False, 'message': 'Category not found.'}, status=404)

    data = CategorySerializer(cat).data
    children = Category.objects(parent_id=str(cat.id), is_active=True)
    data['children'] = CategorySerializer(list(children), many=True).data
    return ok(data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def category_create(request):
    """POST /api/categories/ (Admin)"""
    from datetime import datetime
    name_en = request.data.get('name_en', '')
    name_ja = request.data.get('name_ja', '')
    slug = request.data.get('slug', '')
    parent_id = request.data.get('parent_id')

    if not name_en or not slug:
        return Response({'success': False, 'message': 'name_en and slug required.'}, status=400)

    if Category.objects(slug=slug).first():
        return Response({'success': False, 'message': 'Slug already in use.'}, status=400)

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
        parent_id=parent_id,
        ancestors=ancestors,
        depth=depth,
        image_url=request.data.get('image_url') or None,
        display_order=request.data.get('display_order', 0),
    )
    cat.save()
    return ok(CategorySerializer(cat).data, status_code=201)