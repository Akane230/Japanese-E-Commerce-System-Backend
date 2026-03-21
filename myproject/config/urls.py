"""
URL configuration for さくらShop backend API.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Auth
    path('api/auth/', include('apps.users.urls')),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Health check
    path('api/health/', include('config.health')),

    # Products
    path('api/products/', include('apps.products.urls')),

    # Categories
    path('api/categories/', include('apps.categories.urls')),

    # Cart
    path('api/cart/', include('apps.cart.urls')),

    # Orders
    path('api/orders/', include('apps.orders.urls')),
    path('api/payments/', include('apps.payments.urls')),

    # Inventory
    path('api/inventory/', include('apps.inventory.urls')),

    # Reviews
    path('api/reviews/', include('apps.reviews.urls')),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)