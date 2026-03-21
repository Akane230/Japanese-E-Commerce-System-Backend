from django.urls import path
from . import views

urlpatterns = [
    path('', views.create_order, name='order-create'),
    path('list/', views.list_orders, name='order-list'),
    path('number/<str:order_number>/', views.order_by_number, name='order-by-number'),
    path('admin/', views.admin_order_list, name='admin-order-list'),
    path('<str:order_id>/', views.order_detail, name='order-detail'),

    # admin routes
    path('<str:order_id>/cancel/', views.cancel_order_view, name='order-cancel'),
    path('<str:order_id>/status/', views.admin_update_status, name='admin-update-status'),
    path('<str:order_id>/ship/', views.admin_ship_order, name='admin-ship-order'),
]