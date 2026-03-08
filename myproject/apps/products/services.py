"""
Product business logic — search, filtering, slug generation.
"""
import logging
from typing import Optional
from slugify import slugify
from .models import Product
from apps.inventory.models import Inventory

logger = logging.getLogger(__name__)


def get_product_queryset(
    category_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    sort_by: str = '-created_at',
    is_featured: bool = False,
    is_active: bool = True,
    tag: Optional[str] = None,
):
    """Build filtered/sorted product queryset."""
    qs = Product.objects(is_active=is_active)

    if category_id:
        qs = qs.filter(category_ids=category_id)

    if min_price is not None:
        qs = qs.filter(pricing__base_price__gte=min_price)

    if max_price is not None:
        qs = qs.filter(pricing__base_price__lte=max_price)

    if is_featured:
        qs = qs.filter(is_featured=True)

    if tag:
        qs = qs.filter(tags=tag)

    if search:
        # Basic contains search — for production use MongoDB Atlas Search
        qs = qs.filter(name__icontains=search)

    # Sorting
    sort_map = {
        'newest': '-created_at',
        'oldest': 'created_at',
        'price_asc': 'pricing__base_price',
        'price_desc': '-pricing__base_price',
        'rating': '-rating_summary__average',
        'popular': '-rating_summary__count',
        'name': 'name',
    }
    order = sort_map.get(sort_by, sort_by)
    qs = qs.order_by(order)

    return qs


def generate_unique_slug(name: str, existing_id=None) -> str:
    base_slug = slugify(name)
    slug = base_slug
    counter = 1
    while True:
        qs = Product.objects(slug=slug)
        if existing_id:
            qs = qs.filter(id__ne=existing_id)
        if not qs.first():
            return slug
        slug = f'{base_slug}-{counter}'
        counter += 1


def get_product_with_inventory(slug: str) -> dict:
    """Fetch product + inventory data merged."""
    product = Product.objects(slug=slug, is_active=True).first()
    if not product:
        return None

    inventory = Inventory.objects(product_id=str(product.id)).first()
    return {
        'product': product,
        'in_stock': inventory.is_in_stock if inventory else True,
        'quantity_available': inventory.quantity_available if inventory else 0,
        'is_low_stock': inventory.is_low_stock if inventory else False,
    }


def update_product_rating(product_id: str) -> None:
    """Recalculate and persist product rating from reviews."""
    from apps.reviews.models import Review
    reviews = Review.objects(product_id=product_id, is_published=True)
    count = reviews.count()
    if count == 0:
        avg = 0.0
        dist = [0, 0, 0, 0, 0]
    else:
        ratings = [r.rating for r in reviews]
        avg = round(sum(ratings) / len(ratings), 2)
        dist = [ratings.count(i) for i in range(1, 6)]

    product = Product.objects(id=product_id).first()
    if product:
        product.rating_summary.average = avg
        product.rating_summary.count = count
        product.rating_summary.distribution = dist
        product.save()