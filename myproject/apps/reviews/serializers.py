from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    product_id = serializers.CharField(read_only=True)
    product_name = serializers.SerializerMethodField()
    user_id = serializers.CharField(read_only=True)
    user_username = serializers.SerializerMethodField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=300, allow_blank=True, required=False)
    body = serializers.CharField(max_length=5000)
    media = serializers.ListField(child=serializers.URLField(), required=False)
    is_verified_purchase = serializers.BooleanField(read_only=True)
    helpful_count = serializers.SerializerMethodField()
    is_published = serializers.BooleanField(read_only=True)
    moderation_status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def get_id(self, obj):
        return str(obj.id)

    def get_helpful_count(self, obj):
        return len(obj.helpful_votes) if obj.helpful_votes else 0

    def get_product_name(self, obj):
        if hasattr(obj, 'product') and obj.product:
            return obj.product.name
        from apps.products.models import Product
        product = Product.objects(id=obj.product_id).first()
        return product.name if product else obj.product_id

    def get_user_username(self, obj):
        if hasattr(obj, 'user') and obj.user:
            return obj.user.username
        from apps.users.models import User
        user = User.objects(id=obj.user_id).first()
        return user.username if user else obj.user_id


class ReviewCreateSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    order_id = serializers.CharField(allow_blank=True, required=False)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=300, allow_blank=True, required=False)
    body = serializers.CharField(max_length=5000, min_length=10)
    media = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        max_length=5
    )

    def validate_body(self, value):
        import bleach
        return bleach.clean(value, strip=True)