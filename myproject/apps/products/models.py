"""
Product models — supports bilingual descriptions (EN/JA),
multiple currencies, and international shipping.
"""
from datetime import datetime
from typing import Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from mongoengine import (
    Document,
    EmbeddedDocument,
    StringField,
    FloatField,
    BooleanField,
    DateTimeField,
    ListField,
    EmbeddedDocumentField,
    URLField,
    IntField,
    DecimalField,
    FileField,
)
import cloudinary
import cloudinary.uploader
from cloudinary.models import CloudinaryField  # Keep for reference but won't use directly


class BilingualText(EmbeddedDocument):
    """Text content in English and Japanese."""
    en = StringField(default='')
    ja = StringField(default='')

    def get(self, lang='en'):
        return getattr(self, lang, '') or self.en or ''


class ProductMedia(EmbeddedDocument):
    """
    Product media with Cloudinary integration.
    Stores Cloudinary public IDs instead of URLs for flexibility.
    """
    thumbnail = StringField(max_length=255)  # Cloudinary public ID
    images = ListField(StringField(max_length=255))  # List of Cloudinary public IDs
    video_url = StringField(max_length=255)  # Cloudinary public ID for video
    
    def get_thumbnail_url(self, **options):
        """Generate Cloudinary URL with transformations"""
        if not self.thumbnail:
            return None
        default_options = {'width': 300, 'height': 300, 'crop': 'fill', 'quality': 'auto', 'format': 'auto'}
        default_options.update(options)
        return cloudinary.utils.cloudinary_url(self.thumbnail, **default_options)[0]
    
    def get_image_urls(self, obj):
        image_ids = obj.images if not isinstance(obj, dict) else obj.get('images', [])
        cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'sample')
        return [
            f"https://res.cloudinary.com/{cloud_name}/image/upload/{img_id}"
            for img_id in image_ids if img_id
        ]
    
    def get_video_url(self, **options):
        """Generate Cloudinary video URL"""
        if not self.video_url:
            return None
        return cloudinary.utils.cloudinary_url(self.video_url, resource_type='video', **options)[0]
    
    def _validate_image_file(self, file):
        """
        Basic image validation for admin uploads:
        - content type must be image/*
        - size must not exceed configured max (default 5 MB)
        """
        content_type = getattr(file, 'content_type', '') or ''
        size = getattr(file, 'size', None)

        if not content_type.startswith('image/'):
            raise ValidationError('Invalid image format. Only image uploads are allowed.')

        max_bytes = getattr(settings, 'PRODUCT_IMAGE_MAX_BYTES', 5 * 1024 * 1024)
        if size is not None and size > max_bytes:
            raise ValidationError('Image file is too large.')

    def _validate_video_file(self, file):
        """
        Basic video validation for admin uploads.
        """
        content_type = getattr(file, 'content_type', '') or ''
        size = getattr(file, 'size', None)

        if not content_type.startswith('video/'):
            raise ValidationError('Invalid video format. Only video uploads are allowed.')

        max_bytes = getattr(settings, 'PRODUCT_VIDEO_MAX_BYTES', 50 * 1024 * 1024)
        if size is not None and size > max_bytes:
            raise ValidationError('Video file is too large.')

    def upload_thumbnail(self, file, public_id=None, **options):
        """Upload thumbnail to Cloudinary and store public_id."""
        from logging import getLogger

        logger = getLogger(__name__)

        self._validate_image_file(file)

        try:
            file_data = file

            upload_options = {
                'folder': 'products/thumbnails',
                'resource_type': 'image',
                'unique_filename': True,
            }
            upload_options.update(options)

            if public_id:
                upload_options['public_id'] = public_id

            result = cloudinary.uploader.upload(file_data, **upload_options)
            self.thumbnail = result['public_id']
            return result
        except ValidationError:
            # Bubble up validation issues untouched
            raise
        except Exception as e:
            logger.error(f"Cloudinary thumbnail upload error: {str(e)}")
            raise
    
    def upload_image(self, file, public_id=None, **options):
        """Upload single image to Cloudinary."""
        from logging import getLogger

        logger = getLogger(__name__)

        self._validate_image_file(file)

        try:
            file_data = file

            upload_options = {
                'folder': 'products/images',
                'resource_type': 'image',
                'unique_filename': True,
            }
            upload_options.update(options)

            if public_id:
                upload_options['public_id'] = public_id

            result = cloudinary.uploader.upload(file_data, **upload_options)

            if not self.images:
                self.images = []
            self.images.append(result['public_id'])
            return result
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Cloudinary image upload error: {str(e)}")
            raise

    def upload_images(self, files: Iterable, **options):
        """Upload multiple images to Cloudinary."""
        from logging import getLogger

        logger = getLogger(__name__)

        results = []
        errors = []
        for file in files:
            try:
                result = self.upload_image(file, **options)
                results.append(result)
            except ValidationError as e:
                # Collect validation errors but continue with remaining files
                logger.warning(f"Validation error during image upload: {e}")
                errors.append(str(e))
                continue
            except Exception as e:
                logger.error(f"Failed to upload image: {str(e)}")
                errors.append('Upload failed')
                continue

        # If all uploads failed, raise a combined error for the caller
        if errors and not results:
            raise ValidationError(f"Image uploads failed: {'; '.join(errors)}")

        return results

    def upload_video(self, file, public_id=None, **options):
        """Upload video to Cloudinary."""
        from logging import getLogger

        logger = getLogger(__name__)

        self._validate_video_file(file)

        try:
            file_data = file

            upload_options = {
                'folder': 'products/videos',
                'resource_type': 'video',
                'chunk_size': 6000000,
                'unique_filename': True,
            }
            upload_options.update(options)

            if public_id:
                upload_options['public_id'] = public_id

            result = cloudinary.uploader.upload(file_data, **upload_options)
            self.video_url = result['public_id']
            return result
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Cloudinary video upload error: {str(e)}")
            raise
    
    def delete_thumbnail(self):
        """Delete thumbnail from Cloudinary"""
        if self.thumbnail:
            cloudinary.uploader.destroy(self.thumbnail)
            self.thumbnail = None
    
    def delete_image(self, public_id):
        """Delete specific image from Cloudinary"""
        if public_id in self.images:
            cloudinary.uploader.destroy(public_id)
            self.images.remove(public_id)
    
    def delete_all_images(self):
        """Delete all images from Cloudinary"""
        for img_id in self.images:
            cloudinary.uploader.destroy(img_id)
        self.images = []
    
    def delete_video(self):
        """Delete video from Cloudinary"""
        if self.video_url:
            cloudinary.uploader.destroy(self.video_url, resource_type='video')
            self.video_url = None


class ProductPricing(EmbeddedDocument):
    base_price = DecimalField(required=True, precision=2, min_value=0)
    sale_price = DecimalField(precision=2, min_value=0)
    currency = StringField(max_length=3, default='JPY')   # ISO 4217
    tax_rate = FloatField(default=0.10)                   # e.g. 0.10 = 10%
    tax_included = BooleanField(default=True)             # Japan: tax included

    def get_effective_price(self):
        """Returns active sale price or base price."""
        if self.sale_price and self.sale_price > 0:
            return float(self.sale_price)
        return float(self.base_price)

    def get_price_excluding_tax(self):
        if self.tax_included:
            return self.get_effective_price() / (1 + self.tax_rate)
        return self.get_effective_price()


class StorageInstructions(EmbeddedDocument):
    en = StringField()
    ja = StringField()


class ProductAttributes(EmbeddedDocument):
    weight_grams = IntField(min_value=0)
    brand = StringField(max_length=200)
    certifications = ListField(StringField(max_length=100))
    ingredients = ListField(StringField(max_length=200))
    allergens = ListField(StringField(max_length=100))
    shelf_life_days = IntField(min_value=0)
    storage_instructions = EmbeddedDocumentField(StorageInstructions)
    country_of_origin = StringField(max_length=100, default='Japan')
    barcode = StringField(max_length=50)
    net_weight_grams = IntField(min_value=0)


class ProductShipping(EmbeddedDocument):
    weight_kg = FloatField(min_value=0)
    dimensions_cm = StringField(max_length=50)   # LxWxH
    requires_cold_chain = BooleanField(default=False)
    ships_internationally = BooleanField(default=True)
    domestic_only = BooleanField(default=False)
    prohibited_countries = ListField(StringField(max_length=3))  # ISO codes
    handling_days = IntField(default=2)


class RatingSummary(EmbeddedDocument):
    average = FloatField(default=0.0, min_value=0, max_value=5)
    count = IntField(default=0, min_value=0)
    distribution = ListField(IntField(default=0))  # [1★,2★,3★,4★,5★] counts


class Product(Document):
    """
    Product document.
    Supports bilingual content, multiple currencies, international shipping.
    """
    # Identity
    sku = StringField(max_length=100, required=True, unique=True)
    name = StringField(max_length=500, required=True)
    slug = StringField(max_length=600, required=True, unique=True)
    category_ids = ListField(StringField())  # References to Category._id

    # Bilingual content
    description = EmbeddedDocumentField(BilingualText, default=BilingualText)

    # Media with Cloudinary
    media = EmbeddedDocumentField(ProductMedia, default=ProductMedia)

    # Pricing
    pricing = EmbeddedDocumentField(ProductPricing, required=True)

    # Physical attributes
    attributes = EmbeddedDocumentField(ProductAttributes, default=ProductAttributes)

    # Shipping
    shipping = EmbeddedDocumentField(ProductShipping, default=ProductShipping)

    # Ratings (denormalized for performance)
    rating_summary = EmbeddedDocumentField(RatingSummary, default=RatingSummary)

    # Discovery
    tags = ListField(StringField(max_length=50))
    search_keywords = ListField(StringField(max_length=100))  # For text search

    # Status
    is_active = BooleanField(default=True)
    is_featured = BooleanField(default=False)
    is_new_arrival = BooleanField(default=False)

    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'products',
        'indexes': [
            {'fields': ['slug'], 'unique': True},
            {'fields': ['sku'], 'unique': True},
            {'fields': ['category_ids']},
            {'fields': ['is_active', 'is_featured']},
            {'fields': ['tags']},
            {'fields': ['-created_at']},
            {'fields': ['$name'], 'default_language': 'english'},  # text index
        ],
        'ordering': ['-created_at'],
    }

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.sku})'
    
    def get_primary_image(self, **options):
        """Get primary product image (first image or thumbnail)"""
        if self.media and self.media.images:
            return self.media.get_image_urls(limit=1, **options)[0]
        elif self.media and self.media.thumbnail:
            return self.media.get_thumbnail_url(**options)
        return None
    
    def delete_all_media(self):
        """Delete all Cloudinary media associated with this product"""
        if self.media:
            self.media.delete_thumbnail()
            self.media.delete_all_images()
            self.media.delete_video()