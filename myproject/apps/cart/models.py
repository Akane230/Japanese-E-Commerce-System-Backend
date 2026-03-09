# apps/cart/models.py
from datetime import datetime
from mongoengine import Document, StringField, IntField, DateTimeField, ListField, EmbeddedDocument, EmbeddedDocumentField


class CartItem(EmbeddedDocument):
    product_id = StringField(required=True)
    quantity = IntField(required=True, min_value=1)
    added_at = DateTimeField(default=datetime.utcnow)


class Cart(Document):
    """Persistent cart for authenticated users."""
    user_id = StringField(required=True, unique=True)  # Reference to User._id
    items = ListField(EmbeddedDocumentField(CartItem), default=list)
    updated_at = DateTimeField(default=datetime.utcnow)
    created_at = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'carts',
        'indexes': [
            {'fields': ['user_id'], 'unique': True},
            {'fields': ['updated_at']},
        ]
    }
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    
    def get_item_count(self):
        return sum(item.quantity for item in self.items)
    
    def get_subtotal(self):
        # This would need product lookup, better handled in services
        pass