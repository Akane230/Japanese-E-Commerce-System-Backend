# apps/products/management/commands/test_cloudinary.py
from django.core.management.base import BaseCommand
import cloudinary
import cloudinary.api

class Command(BaseCommand):
    help = 'Test Cloudinary connection'

    def handle(self, *args, **options):
        try:
            # Test ping
            result = cloudinary.api.ping()
            self.stdout.write(self.style.SUCCESS(f'✓ Cloudinary connection successful: {result}'))
            
            # Test account info (requires API permissions)
            try:
                account = cloudinary.api.account()
                self.stdout.write(self.style.SUCCESS(f'✓ Account name: {account.get("name", "N/A")}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠ Account info not available (need API permissions): {str(e)}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Cloudinary connection failed: {str(e)}'))
            self.stdout.write(self.style.ERROR('\nDebug info:'))
            from django.conf import settings
            self.stdout.write(f'  CLOUDINARY_CLOUD_NAME: {settings.CLOUDINARY_CLOUD_NAME}')
            self.stdout.write(f'  CLOUDINARY_API_KEY: {"***" if settings.CLOUDINARY_API_KEY else "NOT SET"}')
            self.stdout.write(f'  CLOUDINARY_API_SECRET: {"***" if settings.CLOUDINARY_API_SECRET else "NOT SET"}')
