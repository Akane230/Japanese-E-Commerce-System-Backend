from datetime import datetime
from mongoengine import Document, StringField, IntField, DateTimeField, BooleanField


class Inventory(Document):
    """
    Real-time inventory tracking per product.
    Prevents overselling through reserved quantity system.
    """
    product_id = StringField(required=True, unique=True)

    quantity_available = IntField(default=0, min_value=0)
    quantity_reserved = IntField(default=0, min_value=0)   # In checkout (not yet ordered)
    quantity_sold = IntField(default=0, min_value=0)

    # Reorder management
    reorder_threshold = IntField(default=10)    # Alert when stock falls below this
    reorder_quantity = IntField(default=50)     # Suggested reorder amount

    is_tracked = BooleanField(default=True)     # False = unlimited stock
    allow_backorder = BooleanField(default=False)

    last_restocked_at = DateTimeField()
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'inventory',
        'indexes': [
            {'fields': ['product_id'], 'unique': True},
            {'fields': ['quantity_available']},
        ]
    }

    @property
    def quantity_on_hand(self):
        """Actual stock: available + reserved."""
        return self.quantity_available + self.quantity_reserved

    @property
    def is_in_stock(self):
        if not self.is_tracked:
            return True
        return self.quantity_available > 0 or self.allow_backorder

    @property
    def is_low_stock(self):
        return self.is_tracked and self.quantity_available <= self.reorder_threshold

    def can_fulfill(self, quantity: int) -> bool:
        if not self.is_tracked:
            return True
        return self.quantity_available >= quantity

    def reserve(self, quantity: int) -> bool:
        """Reserve stock during checkout. Returns False if insufficient."""
        if not self.can_fulfill(quantity):
            return False
        self.quantity_available -= quantity
        self.quantity_reserved += quantity
        self.save()
        return True

    def confirm_sale(self, quantity: int) -> None:
        """Move from reserved to sold on order confirmation."""
        actual = min(quantity, self.quantity_reserved)
        self.quantity_reserved -= actual
        self.quantity_sold += actual
        self.save()

    def release_reservation(self, quantity: int) -> None:
        """Release reservation on cart abandonment/order cancel."""
        actual = min(quantity, self.quantity_reserved)
        self.quantity_reserved -= actual
        self.quantity_available += actual
        self.save()

    def restock(self, quantity: int) -> None:
        self.quantity_available += quantity
        self.last_restocked_at = datetime.utcnow()
        self.save()

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)