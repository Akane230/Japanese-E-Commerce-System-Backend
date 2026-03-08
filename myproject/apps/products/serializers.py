from rest_framework import serializers
from .models import Product


class BilingualTextField(serializers.Serializer):
    en = serializers.CharField(allow_blank=True, required=False)
    ja = serializers.CharField(allow_blank=True, required=False)


class ProductPricingSerializer(serializers.Serializer):
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    sale_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True, required=False)
    currency = serializers.CharField(max_length=3, default='JPY')
    tax_rate = serializers.FloatField(default=0.10)
    tax_included = serializers.BooleanField(default=True)
    effective_price = serializers.SerializerMethodField()

    def get_effective_price(self, obj):
        if isinstance(obj, dict):
            sale = obj.get('sale_price')
            base = obj.get('base_price')
        else:
            sale = getattr(obj, 'sale_price', None)
            base = getattr(obj, 'base_price', 0)
        if sale and float(sale) > 0:
            return float(sale)
        return float(base) if base else 0


class ProductAttributesSerializer(serializers.Serializer):
    weight_grams = serializers.IntegerField(allow_null=True, required=False)
    brand = serializers.CharField(max_length=200, allow_blank=True, required=False)
    certifications = serializers.ListField(child=serializers.CharField(), required=False)
    ingredients = serializers.ListField(child=serializers.CharField(), required=False)
    allergens = serializers.ListField(child=serializers.CharField(), required=False)
    shelf_life_days = serializers.IntegerField(allow_null=True, required=False)
    storage_instructions = BilingualTextField(required=False)
    country_of_origin = serializers.CharField(max_length=100, required=False)


class ProductShippingSerializer(serializers.Serializer):
    weight_kg = serializers.FloatField(allow_null=True, required=False)
    requires_cold_chain = serializers.BooleanField(default=False)
    ships_internationally = serializers.BooleanField(default=True)
    domestic_only = serializers.BooleanField(default=False)
    handling_days = serializers.IntegerField(default=2)


class ProductMediaSerializer(serializers.Serializer):
    thumbnail = serializers.URLField(allow_blank=True, required=False)
    images = serializers.ListField(child=serializers.URLField(), required=False)
    video_url = serializers.URLField(allow_blank=True, required=False)


class RatingSummarySerializer(serializers.Serializer):
    average = serializers.FloatField()
    count = serializers.IntegerField()


class ProductListSerializer(serializers.Serializer):
    """Lightweight serializer for product grid/listing."""
    id = serializers.SerializerMethodField()
    sku = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    thumbnail = serializers.SerializerMethodField()
    pricing = ProductPricingSerializer()
    rating_summary = RatingSummarySerializer()
    is_featured = serializers.BooleanField()
    is_active = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.CharField())
    brand = serializers.SerializerMethodField()
    ships_internationally = serializers.SerializerMethodField()
    category_ids = serializers.ListField(child=serializers.CharField())

    def get_id(self, obj):
        return str(obj.id)

    def get_thumbnail(self, obj):
        if obj.media:
            return obj.media.thumbnail
        return None

    def get_brand(self, obj):
        if obj.attributes:
            return obj.attributes.brand
        return None

    def get_ships_internationally(self, obj):
        if obj.shipping:
            return obj.shipping.ships_internationally
        return True


class ProductDetailSerializer(serializers.Serializer):
    """Full product detail serializer."""
    id = serializers.SerializerMethodField()
    sku = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    category_ids = serializers.ListField(child=serializers.CharField())
    description = BilingualTextField()
    media = ProductMediaSerializer()
    pricing = ProductPricingSerializer()
    attributes = ProductAttributesSerializer()
    shipping = ProductShippingSerializer()
    rating_summary = RatingSummarySerializer()
    tags = serializers.ListField(child=serializers.CharField())
    is_active = serializers.BooleanField()
    is_featured = serializers.BooleanField()
    is_new_arrival = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_id(self, obj):
        return str(obj.id)


class ProductCreateSerializer(serializers.Serializer):
    """Admin: create/update product."""
    sku = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=500)
    slug = serializers.CharField(max_length=600, required=False)
    category_ids = serializers.ListField(child=serializers.CharField(), required=False)
    description = BilingualTextField(required=False)
    media = ProductMediaSerializer(required=False)
    pricing = ProductPricingSerializer()
    attributes = ProductAttributesSerializer(required=False)
    shipping = ProductShippingSerializer(required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    is_active = serializers.BooleanField(default=True)
    is_featured = serializers.BooleanField(default=False)

    def validate_sku(self, value):
        sku = value.upper().strip()
        instance = self.instance
        qs = Product.objects(sku=sku)
        if instance:
            qs = qs.filter(id__ne=instance.id)
        if qs.first():
            raise serializers.ValidationError('SKU already exists.')
        return sku

    def validate_slug(self, value):
        instance = self.instance
        qs = Product.objects(slug=value)
        if instance:
            qs = qs.filter(id__ne=instance.id)
        if qs.first():
            raise serializers.ValidationError('Slug already in use.')
        return value