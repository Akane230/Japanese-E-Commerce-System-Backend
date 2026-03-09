from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_view, name='cart-view'),
    path('add/', views.cart_add, name='cart-add'),
    path('update/', views.cart_update, name='cart-update'),
    path('remove/', views.cart_remove, name='cart-remove'),
    path('clear/', views.cart_clear, name='cart-clear'),
]