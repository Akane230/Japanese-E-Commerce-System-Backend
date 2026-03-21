from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='auth-register'),
    path('login/', views.login, name='auth-login'),
    path('admin-login/', views.adminLogin, name='auth-admin-login'),
    path('logout/', views.logout, name='auth-logout'),
    path('me/', views.me, name='auth-me'),
    path('profile/', views.update_profile, name='auth-profile'),
    path('change-password/', views.change_password, name='auth-change-password'),
    path('addresses/', views.add_address_view, name='auth-add-address'),
    path('addresses/<int:idx>/', views.remove_address_view, name='auth-remove-address'),
    path('addresses/<int:idx>/update/', views.update_address_view, name='auth-update-address'),
    path('addresses/<int:idx>/set-default/', views.set_default_address_view, name='auth-set-default-address'),
    path('wishlist/<str:product_id>/', views.toggle_wishlist_view, name='auth-wishlist'),
]