# apps/cart/services.py
from django.conf import settings
from .models import Cart, CartItem
from apps.users.models import User
from apps.products.models import Product
from apps.inventory.models import Inventory

CART_SESSION_KEY = getattr(settings, 'CART_SESSION_KEY', 'sakura_cart')


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
        # Check if item already in user cart
        existing_item = next(
            (i for i in user_cart.items if i.product_id == product_id), 
            None
        )
        
        if existing_item:
            # Sum quantities (capped by inventory)
            existing_item.quantity += item['quantity']
        else:
            # Add new item
            user_cart.items.append(CartItem(
                product_id=product_id,
                quantity=item['quantity']
            ))
    
    user_cart.save()
    return user_cart


def add_to_cart(request, product_id: str, quantity: int = 1):
    """Add item to cart - handles both auth states."""
    if request.user.is_authenticated:
        cart = get_or_create_user_cart(str(request.user.id))
        
        # Check if product already in cart
        existing_item = next(
            (i for i in cart.items if i.product_id == product_id), 
            None
        )
        
        if existing_item:
            existing_item.quantity += quantity
        else:
            cart.items.append(CartItem(
                product_id=product_id,
                quantity=quantity
            ))
        
        cart.save()
        return cart
    else:
        # Session-based cart for guests
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
    """Update item quantity."""
    if request.user.is_authenticated:
        cart = get_or_create_user_cart(str(request.user.id))
        
        if quantity <= 0:
            # Remove item
            cart.items = [i for i in cart.items if i.product_id != product_id]
        else:
            # Update quantity
            for item in cart.items:
                if item.product_id == product_id:
                    item.quantity = quantity
                    break
        
        cart.save()
        return cart
    else:
        # Session cart
        cart = get_session_cart(request)
        pid = str(product_id)
        
        if quantity <= 0:
            cart.pop(pid, None)
        else:
            cart[pid] = {'quantity': quantity}
        
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
        return cart


def get_enriched_cart(request):
    """Get cart with product details - works for both auth states."""
    from apps.products.models import Product
    from apps.inventory.models import Inventory
    
    items = []
    subtotal = 0.0
    
    if request.user.is_authenticated:
        # Get from database
        cart = get_or_create_user_cart(str(request.user.id))
        cart_items = [(item.product_id, item.quantity) for item in cart.items]
    else:
        # Get from session
        cart = get_session_cart(request)
        cart_items = [(pid, item['quantity']) for pid, item in cart.items()]
    
    for product_id, quantity in cart_items:
        try:
            product = Product.objects(id=product_id, is_active=True).first()
            if not product:
                continue
            
            price = product.pricing.get_effective_price()
            item_subtotal = price * quantity
            subtotal += item_subtotal
            
            inv = Inventory.objects(product_id=product_id).first()
            
            items.append({
                'product_id': product_id,
                'sku': product.sku,
                'name': product.name,
                'name_ja': product.description.ja if product.description else '',
                'thumbnail': product.media.thumbnail if product.media else '',
                'slug': product.slug,
                'unit_price': price,
                'quantity': quantity,
                'subtotal': item_subtotal,
                'currency': product.pricing.currency,
                'in_stock': inv.is_in_stock if inv else True,
                'max_quantity': inv.quantity_available if inv and inv.is_tracked else 99,
            })
        except Exception:
            continue
    
    return {
        'items': items,
        'item_count': sum(i['quantity'] for i in items),
        'subtotal': round(subtotal, 2),
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
    """Remove item from cart."""
    if request.user.is_authenticated:
        cart = get_or_create_user_cart(request.user.id)
        cart.items = [i for i in cart.items if i.product_id != product_id]
        cart.save()
    else:
        cart = get_session_cart(request)
        pid = str(product_id)
        cart.pop(pid, None)
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True


