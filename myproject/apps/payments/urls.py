from django.urls import path
from . import views

urlpatterns = [
    # Customer-facing
    path('methods/', views.all_payment_instructions, name='payment-methods'),
    path('instructions/<str:order_id>/', views.payment_instructions, name='payment-instructions'),
    path('submit/', views.submit_payment_proof, name='payment-submit-proof'),
    path('upload/', views.upload_payment_proof, name='payment-upload-proof'),

    # Admin-facing
    path('admin/pending/', views.admin_pending_payments, name='admin-pending-payments'),
    path('confirm/<str:order_id>/', views.admin_confirm_payment, name='admin-confirm-payment'),
    path('reject/<str:order_id>/', views.admin_reject_payment, name='admin-reject-payment'),
    path('refund/<str:order_id>/', views.admin_process_refund, name='admin-process-refund'),
]