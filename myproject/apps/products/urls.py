from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product-list'),
    path('featured/', views.product_featured, name='product-featured'),
    path('search/', views.product_search, name='product-search'),
    path('admin/create/', views.product_create, name='product-create'),
    path('<slug:slug>/', views.product_detail, name='product-detail'),
    path('<slug:slug>/admin/', views.product_update, name='product-update'),
    path('<slug:slug>/admin/delete/', views.product_delete, name='product-delete'),
]