from datetime import datetime
from mongoengine import (
    Document, StringField, IntField, BooleanField,
    DateTimeField, ListField, URLField, ReferenceField
)


class Review(Document):
    """
    Product review with verified purchase validation and moderation.
    """
    product_id = StringField(required=True)
    product = ReferenceField('Product', required=True)
    user_id = StringField(required=True)
    user = ReferenceField('User', required=True)
    order_id = StringField()           # Links to Order for verified purchase check

    # Content
    rating = IntField(required=True, min_value=1, max_value=5)
    title = StringField(max_length=300)
    body = StringField(max_length=5000, required=True)
    media = ListField(URLField())       # Images/videos uploaded by reviewer

    # Verification
    is_verified_purchase = BooleanField(default=False)

    # Community
    helpful_votes = ListField(StringField())    # user_ids who voted helpful
    unhelpful_votes = ListField(StringField())  # user_ids who voted unhelpful

    # Moderation
    is_published = BooleanField(default=False)  # Requires mod approval
    moderation_status = StringField(
        max_length=20,
        choices=['pending', 'approved', 'rejected', 'flagged'],
        default='pending'
    )
    moderation_note = StringField(max_length=500)
    moderated_by = StringField()        # Admin user_id
    moderated_at = DateTimeField()

    # Reporter
    reported_by = ListField(StringField())  # user_ids who reported
    report_reason = StringField(max_length=200)

    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'reviews',
        'indexes': [
            {'fields': ['product_id', 'is_published']},
            {'fields': ['user_id']},
            {'fields': ['order_id']},
            {'fields': ['-created_at']},
            {'fields': ['moderation_status']},
        ],
        'ordering': ['-created_at'],
    }

    @property
    def helpful_count(self):
        return len(self.helpful_votes)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Review by user {self.user.username} on product {self.product.name} ({self.rating}★)'