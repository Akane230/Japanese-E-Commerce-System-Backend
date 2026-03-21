import logging

from django.conf import settings
from .models import Cart, CartItem
from apps.users.models import User
from apps.products.models import Product
from apps.inventory.models import Inventory
from bson import ObjectId

logger = logging.getLogger(__name__)
CART_SESSION_KEY = getattr(settings, 'CART_SESSION_KEY', 'sakura_cart')


def _get_thumbnail_url(media) -> str:
    """Build Cloudinary thumbnail URL directly, matching the serializer pattern."""
    if not media or not media.thumbnail:
        return ""
    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
    if not cloud_name:
        return ""
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/c_fill,h_300,w_300,q_auto,f_auto/{media.thumbnail}"


def get_cart(request):
    """Get cart - from session for guests, from DB for authenticated users."""
    if request.user.is_authenticated:
        return get_or_create_user_cart(str(request.user.id))
    return get_session_cart(request)


def get_or_create_user_cart(user_id: str) -> Cart:
    """Get or create persistent cart for authenticated user."""
    cart = Cart.objects(user_id=user_id).first()
    if not cart:
        cart = Cart(user_id=user_id)
        cart.save()
    return cart


def get_session_cart(request) -> dict:
    """Get session-based cart for guests."""
    return request.session.get(CART_SESSION_KEY, {})


def merge_carts(session_cart: dict, user_cart: Cart) -> Cart:
    """Merge guest cart into user cart after login."""
    for product_id, item in session_cart.items():
        existing_item = next(
            (i for i in user_cart.items if i.product_id == product_id), 
            None
        )
        if existing_item:
            existing_item.quantity += item['quantity']
        else:
            user_cart.items.append(CartItem(
                product_id=product_id,
                quantity=item['quantity']
            ))
    user_cart.save()
    return user_cart


def add_to_cart(request, product_id: str, quantity: int = 1):
    """Add item to cart."""
    if request.user.is_authenticated:
        cart = get_or_create_user_cart(str(request.user.id))
        existing_item = next(
            (i for i in cart.items if i.product_id == product_id), None
        )
        if existing_item:
            existing_item.quantity += quantity
        else:
            cart.items.append(CartItem(product_id=product_id, quantity=quantity))
        cart.save()
        return cart
    else:
        cart = get_session_cart(request)
        pid = str(product_id)
        if pid in cart:
            cart[pid]['quantity'] += quantity
        else:
            cart[pid] = {'quantity': quantity}
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
        return cart


def update_cart_item(request, product_id: str, quantity: int):
    """Update item quantity in cart."""
    if quantity <= 0:
        return remove_from_cart(request, product_id)

    if request.user.is_authenticated:
        cart = get_or_create_user_cart(str(request.user.id))
        item_found = False
        for item in cart.items:
            if item.product_id == product_id:
                item.quantity = quantity
                item_found = True
                break
        if not item_found:
            cart.items.append(CartItem(product_id=product_id, quantity=quantity))
        cart.save()
        return cart
    else:
        cart = get_session_cart(request)
        pid = str(product_id)
        cart[pid] = {'quantity': quantity}
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
        return cart


def get_enriched_cart(request):
    """Get cart with full product details."""
    items = []
    subtotal = 0.0

    if request.user.is_authenticated:
        cart = get_or_create_user_cart(str(request.user.id))
        cart_items = [(item.product_id, item.quantity) for item in cart.items]
    else:
        cart = get_session_cart(request)
        cart_items = [(pid, item['quantity']) for pid, item in cart.items()]

    for product_id, quantity in cart_items:
        if not ObjectId.is_valid(product_id):
            logger.warning(f"Skipping invalid product_id: {product_id}")
            continue

        try:
            product = Product.objects(id=product_id, is_active=True).first()
            if not product:
                logger.warning(f"Product not found: {product_id}")
                continue

            price = product.pricing.get_effective_price()
            item_subtotal = price * quantity
            subtotal += item_subtotal

            inv = Inventory.objects(product_id=product_id).first()
            thumbnail_url = _get_thumbnail_url(product.media)

            items.append({
                'product_id': product_id,
                'sku': getattr(product, 'sku', ''),
                'name': product.name,
                'name_ja': product.description.ja if product.description else '',
                'thumbnail': thumbnail_url,
                'image': thumbnail_url,
                'slug': getattr(product, 'slug', ''),
                'unit_price': price,
                'quantity': quantity,
                'subtotal': item_subtotal,
                'currency': getattr(product.pricing, 'currency', 'USD') if product.pricing else 'USD',
                'in_stock': inv.is_in_stock if inv else True,
                'max_quantity': inv.quantity_available if inv and inv.is_tracked else 99,
                'is_available': True,
            })
        except Exception as e:
            logger.error(f"Error processing cart item {product_id}: {e}")
            continue

    return {
        'items': items,
        'item_count': sum(i['quantity'] for i in items),
        'subtotal': float(round(subtotal, 2)),
        'is_authenticated': request.user.is_authenticated
    }


def clear_cart(request):
    """Clear cart."""
    if request.user.is_authenticated:
        cart = get_or_create_user_cart(str(request.user.id))
        cart.items = []
        cart.save()
    else:
        request.session[CART_SESSION_KEY] = {}
        request.session.modified = True


def remove_from_cart(request, product_id: str):
    """Remove item from cart completely."""
    if request.user.is_authenticated:
        cart = get_or_create_user_cart(str(request.user.id))
        cart.items = [i for i in cart.items if i.product_id != product_id]
        cart.save()
        return cart
    else:
        cart = get_session_cart(request)
        pid = str(product_id)
        if pid in cart:
            cart.pop(pid, None)
            request.session[CART_SESSION_KEY] = cart
            request.session.modified = True
        return cart