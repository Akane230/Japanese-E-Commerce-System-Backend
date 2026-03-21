from django.core.management.base import BaseCommand
from apps.cart.models import Cart, CartItem
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up invalid product IDs from carts'

    def handle(self, *args, **options):
        self.stdout.write('Starting cart cleanup...')
        
        cleaned_carts = 0
        cleaned_items = 0
        
        # Clean up authenticated user carts
        for cart in Cart.objects():
            original_count = len(cart.items)
            valid_items = []
            
            for item in cart.items:
                if ObjectId.is_valid(item.product_id):
                    valid_items.append(item)
                else:
                    cleaned_items += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Removed invalid product_id {item.product_id} from cart {cart.id}'
                        )
                    )
            
            if len(valid_items) != original_count:
                cart.items = valid_items
                cart.save()
                cleaned_carts += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Cleanup complete: {cleaned_carts} carts cleaned, {cleaned_items} invalid items removed'
            )
        )
