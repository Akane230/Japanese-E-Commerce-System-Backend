from django.urls import path
from . import views

urlpatterns = [
    path('', views.create_review, name='review-create'),
    path('product/<str:product_id>/', views.product_reviews, name='product-reviews'),
    path('<str:review_id>/helpful/', views.vote_helpful, name='review-helpful'),
    path('admin/', views.admin_reviews_list, name='admin-reviews-list'),
    path('admin/pending/', views.admin_pending_reviews, name='admin-pending-reviews'),
    path('admin/<str:review_id>/moderate/', views.admin_moderate_review, name='admin-moderate-review'),
]