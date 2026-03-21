from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_inventory_list, name='inventory-list'),
    path('low-stock/', views.admin_low_stock_list, name='inventory-low-stock'),
    path('<str:product_id>/stock/', views.stock_check, name='stock-check'),
    path('<str:product_id>/', views.admin_inventory_detail, name='inventory-detail'),
    path('<str:product_id>/restock/', views.admin_restock, name='inventory-restock'),
    path('<str:product_id>/update/', views.admin_update_inventory, name='inventory-update'),
]