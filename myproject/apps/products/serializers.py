from rest_framework import serializers
from django.conf import settings
from .models import Product
import cloudinary 


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
    """Serializer for product media - now using Cloudinary public IDs"""
    thumbnail = serializers.CharField(allow_blank=True, required=False)  # Changed from URLField
    images = serializers.ListField(child=serializers.CharField(), required=False)  # Changed from URLField
    video_url = serializers.CharField(allow_blank=True, required=False)  # Changed from URLField
    
    # Add computed fields for URLs
    thumbnail_url = serializers.SerializerMethodField()
    image_urls = serializers.SerializerMethodField()
    video_url_full = serializers.SerializerMethodField()
    
    def get_thumbnail_url(self, obj):
        if isinstance(obj, dict):
            thumbnail_id = obj.get('thumbnail')
        else:
            thumbnail_id = getattr(obj, 'thumbnail', None)
        
        if thumbnail_id:
            cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'sample')
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{thumbnail_id}"
        return None
    
    def get_image_urls(self, obj):
        if isinstance(obj, dict):
            image_ids = obj.get('images', [])
        else:
            image_ids = getattr(obj, 'images', [])
        
        urls = []
        request = self.context.get('request')
        width = request.GET.get('image_width', 800) if request else 800
        cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'sample')
        
        for img_id in image_ids:
            url = f"https://res.cloudinary.com/{cloud_name}/image/upload/w_{width}/{img_id}"
            urls.append(url)
        return urls
    
    def get_video_url_full(self, obj):
        if isinstance(obj, dict):
            video_id = obj.get('video_url')
        else:
            video_id = getattr(obj, 'video_url', None)
        
        if video_id:
            cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'sample')
            return f"https://res.cloudinary.com/{cloud_name}/video/upload/{video_id}"
        return None


class RatingSummarySerializer(serializers.Serializer):
    average = serializers.FloatField()
    count = serializers.IntegerField()


class ProductListSerializer(serializers.Serializer):
    """Lightweight serializer for product grid/listing."""
    id = serializers.SerializerMethodField()
    sku = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    thumbnail_url = serializers.SerializerMethodField()
    pricing = ProductPricingSerializer()
    rating_summary = RatingSummarySerializer()
    is_featured = serializers.BooleanField()
    is_active = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.CharField())
    brand = serializers.SerializerMethodField()
    ships_internationally = serializers.SerializerMethodField()
    category_ids = serializers.ListField(child=serializers.CharField())
    category_names = serializers.SerializerMethodField()

    def get_id(self, obj):
        return str(obj.id)

    def get_thumbnail_url(self, obj):
        """Get optimized thumbnail URL for listings"""
        # Check if obj has media and thumbnail
        if hasattr(obj, 'media') and obj.media:
            if obj.media.thumbnail:
                cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
                if cloud_name:
                    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{obj.media.thumbnail}"
                else:
                    # Fallback to sample cloud for demo
                    return f"https://res.cloudinary.com/sample/image/upload/{obj.media.thumbnail}"
            
            # If no thumbnail but there are images, use the first image
            if obj.media.images and len(obj.media.images) > 0:
                cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
                if cloud_name:
                    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{obj.media.images[0]}"
                else:
                    return f"https://res.cloudinary.com/sample/image/upload/{obj.media.images[0]}"
        
        return None

    def get_brand(self, obj):
        if obj.attributes:
            return obj.attributes.brand
        return None

    def get_ships_internationally(self, obj):
        if obj.shipping:
            return obj.shipping.ships_internationally
        return True

    def get_category_names(self, obj):
        """Fetch category names for the given category IDs"""
        from apps.categories.models import Category
        if not obj.category_ids:
            return []
        
        categories = Category.objects(id__in=obj.category_ids)
        return [cat.name.en for cat in categories if cat.name]


class ProductDetailSerializer(serializers.Serializer):
    """Full product detail serializer."""
    id = serializers.SerializerMethodField()
    sku = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    category_ids = serializers.ListField(child=serializers.CharField())
    description = BilingualTextField()
    media = ProductMediaSerializer()  # Will now include URLs via SerializerMethodFields
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
    """Admin: create/update product - now accepts file uploads"""
    sku = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=500)
    slug = serializers.CharField(max_length=600, required=False, allow_blank=True)
    category_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    description = BilingualTextField(required=False, allow_null=True)
    
    # Media fields for file uploads
    thumbnail_file = serializers.FileField(required=False, write_only=True, allow_null=True)
    image_files = serializers.ListField(
        child=serializers.FileField(), 
        required=False, 
        write_only=True,
        allow_empty=True
    )
    video_file = serializers.FileField(required=False, write_only=True, allow_null=True)
    
    media = ProductMediaSerializer(required=False, allow_null=True)

    # special update flags - frontend may request removal of existing files
    remove_thumbnail = serializers.BooleanField(required=False, write_only=True, default=False)
    remove_video = serializers.BooleanField(required=False, write_only=True, default=False)
    
    pricing = ProductPricingSerializer(required=True)  # Pricing is required
    attributes = ProductAttributesSerializer(required=False, allow_null=True)
    shipping = ProductShippingSerializer(required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    search_keywords = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    is_active = serializers.BooleanField(default=True)
    is_featured = serializers.BooleanField(default=False)
    is_new_arrival = serializers.BooleanField(default=False)

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