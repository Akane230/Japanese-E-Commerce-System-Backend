import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response

from config.exceptions import success_response, error_response
from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer
from apps.products.services import update_product_rating
from apps.orders.models import Order
from config.pagination import StandardPagination

logger = logging.getLogger(__name__)


def ok(data=None, message: str = '', status_code: int = status.HTTP_200_OK):
    return success_response(data=data, message=message, status_code=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
def product_reviews(request, product_id):
    """GET /api/reviews/product/<product_id>/"""
    qs = Review.objects(product_id=product_id, is_published=True).order_by('-created_at').select_related()

    sort_by = request.query_params.get('sort_by', 'newest')
    if sort_by == 'helpful':
        reviews = sorted(list(qs), key=lambda r: len(r.helpful_votes), reverse=True)
    elif sort_by == 'rating_high':
        reviews = sorted(list(qs), key=lambda r: r.rating, reverse=True)
    elif sort_by == 'rating_low':
        reviews = sorted(list(qs), key=lambda r: r.rating)
    else:
        reviews = list(qs)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(reviews, request)
    return paginator.get_paginated_response(ReviewSerializer(page, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_review(request):
    """POST /api/reviews/"""
    from apps.products.models import Product
    user_id = str(request.user.id)
    serializer = ReviewCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            error='ValidationError',
            message='Invalid review data.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            errors=serializer.errors,
        )

    data = serializer.validated_data
    product_id = data['product_id']
    order_id = data.get('order_id')

    # Prevent duplicate reviews
    if Review.objects(product_id=product_id, user_id=user_id).first():
        return error_response(
            error='Conflict',
            message='You have already reviewed this product.',
            status_code=status.HTTP_409_CONFLICT,
        )

    # Check verified purchase
    is_verified = False
    if order_id:
        order = Order.objects(id=order_id, user_id=user_id).first()
        if order and any(str(item.product_id) == product_id for item in order.items):
            if order.status in ('delivered', 'shipped'):
                is_verified = True

    product = Product.objects(id=product_id).first()
    if not product:
        return error_response(
            error='NotFound',
            message='Product not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    review = Review(
        product_id=product_id,
        product=product,
        user_id=user_id,
        user=request.user,
        order_id=order_id,
        rating=data['rating'],
        title=data.get('title', ''),
        body=data['body'],
        media=data.get('media', []),
        is_verified_purchase=is_verified,
        is_published=False,    # Requires moderation
        moderation_status='pending',
    )
    review.save()

    return ok(ReviewSerializer(review).data, 'Review submitted. Pending moderation.', 201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vote_helpful(request, review_id):
    """POST /api/reviews/<id>/helpful/"""
    user_id = str(request.user.id)
    review = Review.objects(id=review_id, is_published=True).first()
    if not review:
        return error_response(
            error='NotFound',
            message='Review not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if user_id in review.helpful_votes:
        review.helpful_votes.remove(user_id)
        voted = False
    else:
        review.helpful_votes.append(user_id)
        review.unhelpful_votes = [v for v in review.unhelpful_votes if v != user_id]
        voted = True

    review.save()
    return ok({'helpful_count': len(review.helpful_votes), 'voted': voted})


# ─────────────────────────────────────────────
# Admin moderation
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_pending_reviews(request):
    """GET /api/reviews/admin/pending/"""
    qs = Review.objects(moderation_status='pending').order_by('created_at').select_related()
    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(qs), request)
    return paginator.get_paginated_response(ReviewSerializer(page, many=True).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_moderate_review(request, review_id):
    """POST /api/reviews/admin/<id>/moderate/"""
    from datetime import datetime
    review = Review.objects(id=review_id).first()
    if not review:
        return error_response(
            error='NotFound',
            message='Review not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    action = request.data.get('action')  # 'approve' or 'reject'
    note = request.data.get('note', '')

    if action == 'approve':
        review.moderation_status = 'approved'
        review.is_published = True
    elif action == 'reject':
        review.moderation_status = 'rejected'
        review.is_published = False
    else:
        return error_response(
            error='ValidationError',
            message="action must be 'approve' or 'reject'.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    review.moderation_note = note
    review.moderated_by = str(request.user.id)
    review.moderated_at = datetime.utcnow()
    review.save()

    if action == 'approve':
        update_product_rating(review.product_id)

    return ok(ReviewSerializer(review).data, message=f'Review {action}d.')

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_reviews_list(request):
    """GET /api/reviews/admin/?moderation_status=approved|rejected|pending"""
    moderation_status = request.query_params.get('moderation_status', 'pending')
    qs = Review.objects(moderation_status=moderation_status).order_by('-created_at').select_related()
    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(qs), request)
    return paginator.get_paginated_response(ReviewSerializer(page, many=True).data)