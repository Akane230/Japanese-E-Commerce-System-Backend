# config/cloudinary_config.py
"""
Cloudinary configuration for Django + MongoDB
"""
import cloudinary
import cloudinary.api
import cloudinary.uploader
from django.conf import settings


def configure_cloudinary():
    """Configure Cloudinary with settings from Django settings"""
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )


def get_cloudinary_url(public_id, **options):
    """Helper to generate Cloudinary URLs with default options"""
    default_options = {
        'quality': 'auto',
        'format': 'auto'
    }
    default_options.update(options)
    return cloudinary.utils.cloudinary_url(public_id, **default_options)[0]