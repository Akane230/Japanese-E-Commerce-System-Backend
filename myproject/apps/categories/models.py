from datetime import datetime
from mongoengine import (
    Document, EmbeddedDocument, StringField, BooleanField,
    DateTimeField, ListField, IntField, URLField, ObjectIdField
)


class LocalizedName(EmbeddedDocument):
    en = StringField(required=True, max_length=200)
    ja = StringField(max_length=200)

    def get(self, lang='en'):
        return getattr(self, lang, '') or self.en


class Category(Document):
    """
    Product category with nested hierarchy support.
    e.g. Food > Tea > Matcha
    """
    name = EmbeddedDocumentField(LocalizedName, required=True)
    slug = StringField(max_length=300, required=True, unique=True)
    description = EmbeddedDocumentField(LocalizedName)

    # Hierarchy
    parent_id = StringField()                    # Parent category _id (null = root)
    ancestors = ListField(StringField())         # All ancestor _ids (for breadcrumb)
    depth = IntField(default=0)                  # 0=root, 1=child, 2=grandchild

    # Media
    image_url = URLField()
    banner_url = URLField()

    # Display
    display_order = IntField(default=0)
    is_active = BooleanField(default=True)

    # Stats (denormalized)
    product_count = IntField(default=0)

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'categories',
        'indexes': [
            {'fields': ['slug'], 'unique': True},
            {'fields': ['parent_id']},
            {'fields': ['is_active', 'display_order']},
        ],
        'ordering': ['display_order', 'name.en'],
    }

    def get_all_children_ids(self):
        """Return IDs of all descendant categories."""
        children = Category.objects(parent_id=str(self.id))
        ids = [str(self.id)]
        for child in children:
            ids.extend(child.get_all_children_ids())
        return ids

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name.en}'