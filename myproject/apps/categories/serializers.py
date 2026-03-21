from rest_framework import serializers
from .models import Category
from apps.products.models import Product

class CategorySerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    slug = serializers.CharField()
    emoji = serializers.CharField(allow_blank=True, allow_null=True)
    parent_id = serializers.CharField(allow_null=True)
    ancestors = serializers.ListField(child=serializers.CharField())
    depth = serializers.IntegerField()
    image_url = serializers.URLField(allow_blank=True, allow_null=True)
    display_order = serializers.IntegerField()
    product_count = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()

    def get_id(self, obj):
        return str(obj.id)

    def get_name(self, obj):
        if obj.name:
            return {'en': obj.name.en, 'ja': obj.name.ja or obj.name.en}
        return {'en': '', 'ja': ''}

    def get_product_count(self, obj):
        """Calculate active product count for this category"""
        return Product.objects(
            category_ids=str(obj.id),
            is_active=True
        ).count()