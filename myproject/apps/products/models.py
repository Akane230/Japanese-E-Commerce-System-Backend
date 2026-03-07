"""
Product models — supports bilingual descriptions (EN/JA),
multiple currencies, and international shipping.
"""
from datetime import datetime
from mongoengine import (
    Document, EmbeddedDocument, StringField, FloatField,
    BooleanField, DateTimeField, ListField, EmbeddedDocumentField,
    URLField, IntField, DecimalField
)


class BilingualText(EmbeddedDocument):
    """Text content in English and Japanese."""
    en = StringField(default='')
    ja = StringField(default='')

    def get(self, lang='en'):
        return getattr(self, lang, '') or self.en or ''


class ProductMedia(EmbeddedDocument):
    thumbnail = URLField()
    images = ListField(URLField())
    video_url = URLField()


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

    # Media
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