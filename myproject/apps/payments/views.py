"""
Manual Payment System for さくらShop.

Flow:
  1. Customer places order  → status: pending
  2. Customer submits proof of payment (reference number + screenshot URL)
     POST /api/payments/submit/
  3. Admin reviews proof    → status: payment_pending
  4. Admin confirms         POST /api/payments/confirm/   → status: paid
     OR
     Admin rejects          POST /api/payments/reject/    → status: pending (retry)
  5. Admin processes refund POST /api/payments/refund/    → status: refunded

Supported payment methods (all manual / off-platform):
  - gcash          GCash (PH)
  - bank_transfer  Bank / wire transfer
  - cod            Cash on Delivery
  - maya           Maya / PayMaya (PH)
  - instapay       InstaPay (PH)
  - other          Any other manual method
"""
import logging
from datetime import datetime

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from config.exceptions import success_response, error_response
from apps.orders.models import Order
from apps.orders.services import confirm_payment, cancel_order

logger = logging.getLogger(__name__)


MANUAL_PAYMENT_METHODS = ['gcash', 'bank_transfer', 'cod', 'maya', 'instapay', 'other']

# Payment instructions shown to customers per method
PAYMENT_INSTRUCTIONS = {
    'gcash': {
        'label': 'GCash',
        'instructions': [
            'Send payment to GCash number: 0917-XXX-XXXX (さくらShop)',
            'Use your Order Number as the payment note/reference.',
            'Take a screenshot of the successful transaction.',
            'Submit your GCash reference number and screenshot URL below.',
        ],
        'fields_required': ['reference_number', 'proof_url'],
    },
    'maya': {
        'label': 'Maya (PayMaya)',
        'instructions': [
            'Send payment to Maya number: 0917-XXX-XXXX (さくらShop)',
            'Use your Order Number as the payment note/reference.',
            'Take a screenshot of the successful transaction.',
            'Submit your Maya reference number and screenshot URL below.',
        ],
        'fields_required': ['reference_number', 'proof_url'],
    },
    'bank_transfer': {
        'label': 'Bank Transfer',
        'instructions': [
            'Bank: BDO Unibank',
            'Account Name: さくらShop Inc.',
            'Account Number: 1234-5678-9012',
            'Transfer the exact order amount and use your Order Number as reference.',
            'Submit your bank transaction reference number and deposit slip URL below.',
        ],
        'fields_required': ['reference_number', 'proof_url'],
    },
    'instapay': {
        'label': 'InstaPay',
        'instructions': [
            'Send via InstaPay to: sakurashop@unionbank',
            'Use your Order Number as the payment reference.',
            'Submit your InstaPay reference number and screenshot URL below.',
        ],
        'fields_required': ['reference_number', 'proof_url'],
    },
    'cod': {
        'label': 'Cash on Delivery',
        'instructions': [
            'Prepare the exact amount in cash upon delivery.',
            'Payment is collected by the courier at your door.',
            'No advance payment required — your order will be processed immediately.',
        ],
        'fields_required': [],   # No proof needed for COD
    },
    'other': {
        'label': 'Other Payment Method',
        'instructions': [
            'Please contact support@sakurashop.jp to arrange payment.',
            'Include your Order Number in the subject line.',
        ],
        'fields_required': ['reference_number'],
    },
}

def ok(data=None, message: str = '', status_code: int = status.HTTP_200_OK):
    return success_response(data=data, message=message, status_code=status_code)


def err(message: str, status_code: int = status.HTTP_400_BAD_REQUEST, error: str | None = None):
    return error_response(
        error=error or 'Bad Request' if status_code == status.HTTP_400_BAD_REQUEST else 'Error',
        message=message,
        status_code=status_code,
    )


# ─────────────────────────────────────────────────────────────────
# GET PAYMENT INSTRUCTIONS
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_instructions(request, order_id):
    """
    GET /api/payments/instructions/<order_id>/

    Returns payment instructions for the order's selected payment method.
    Called after order creation so the customer knows where/how to pay.
    """
    user_id = str(request.user.id)
    order = Order.objects(id=order_id, user_id=user_id).first()
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    if not order.payment:
        return err(
            'Payment info not found on this order.',
            status_code=status.HTTP_404_NOT_FOUND,
            error='NotFound',
        )

    method = order.payment.method
    info = PAYMENT_INSTRUCTIONS.get(method, PAYMENT_INSTRUCTIONS['other'])

    return ok({
        'order_number': order.order_number,
        'order_id': str(order.id),
        'grand_total': float(order.grand_total),
        'currency': order.currency,
        'payment_method': method,
        'payment_label': info['label'],
        'instructions': info['instructions'],
        'fields_required': info['fields_required'],
        'status': order.payment.status,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_payment_instructions(request):
    """
    GET /api/payments/methods/

    Returns payment instructions for all available methods.
    Used on the checkout page to show customers their options.
    """
    return ok({
        'methods': [
            {
                'method': method,
                'label': info['label'],
                'instructions': info['instructions'],
                'fields_required': info['fields_required'],
            }
            for method, info in PAYMENT_INSTRUCTIONS.items()
        ]
    })


# ─────────────────────────────────────────────────────────────────
# CUSTOMER: SUBMIT PROOF OF PAYMENT
# ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_payment_proof(request):
    """
    POST /api/payments/submit/

    Customer submits their proof of payment after transferring funds.

    Body:
    {
        "order_id":         "...",
        "reference_number": "GCash ref or bank ref",   (required for most methods)
        "proof_url":        "https://...",              (screenshot/receipt URL, optional for COD)
        "notes":            "optional customer note"
    }

    Transitions order status: pending → payment_pending
    """
    user_id = str(request.user.id)
    order_id = request.data.get('order_id')
    reference_number = request.data.get('reference_number', '').strip()
    proof_url = request.data.get('proof_url', '').strip()
    notes = request.data.get('notes', '').strip()

    if not order_id:
        return err(
            'order_id is required.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error='ValidationError',
        )

    order = Order.objects(id=order_id, user_id=user_id).first()
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    if order.payment.status == 'paid':
        return err(
            'This order has already been confirmed as paid.',
            status_code=status.HTTP_409_CONFLICT,
            error='Conflict',
        )

    if order.payment.status == 'payment_pending':
        return err(
            'Payment proof already submitted. Awaiting admin confirmation.',
            status_code=status.HTTP_409_CONFLICT,
            error='Conflict',
        )

    if order.status not in ('pending',):
        return err(
            f'Cannot submit payment for order in status: {order.status}',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Validate required fields per payment method
    method = order.payment.method
    info = PAYMENT_INSTRUCTIONS.get(method, {})
    required_fields = info.get('fields_required', [])

    if 'reference_number' in required_fields and not reference_number:
        return err(
            'reference_number is required for this payment method.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error='ValidationError',
        )

    if 'proof_url' in required_fields and not proof_url:
        return err(
            'proof_url (screenshot/receipt link) is required for this payment method.',
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error='ValidationError',
        )

    # Store proof on the order
    order.payment.transaction_id = reference_number or 'COD'
    order.payment.proof_url = proof_url
    order.payment.submitted_at = datetime.utcnow()

    note = f'Payment proof submitted. Reference: {reference_number or "N/A"}.'
    if notes:
        note += f' Customer note: {notes}'

    order.update_status(
        'payment_pending',
        note=note,
        actor=user_id
    )
    order.save()

    logger.info(
        f'Payment proof submitted for order {order.order_number} '
        f'by user {user_id}. Method: {method}. Ref: {reference_number}'
    )

    return ok({
        'order_number': order.order_number,
        'status': order.status,
        'payment_status': order.payment.status,
        'message': 'Your payment proof has been submitted. '
                   'Our team will confirm your payment within 1–2 business hours.',
    }, message='Payment proof submitted successfully.', status_code=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_payment_proof(request):
    """
    POST /api/payments/upload/

    Upload payment proof image to Cloudinary.

    Body: multipart/form-data with 'file' field containing image.

    Returns: { "url": "https://..." }
    """
    from config.cloudinary_config import configure_cloudinary
    import cloudinary.uploader

    configure_cloudinary()

    file = request.FILES.get('file')
    if not file:
        return err('No file provided.', status_code=status.HTTP_400_BAD_REQUEST)

    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        return err('Invalid file type. Only images are allowed.', status_code=status.HTTP_400_BAD_REQUEST)

    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        return err('File too large. Maximum size is 5MB.', status_code=status.HTTP_400_BAD_REQUEST)

    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file,
            folder='payment_proofs',
            resource_type='image',
            quality='auto'
        )
        url = result.get('secure_url')
        if not url:
            return err('Upload failed.', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return ok({'url': url}, message='Image uploaded successfully.')
    except Exception as e:
        logger.exception(f'Cloudinary upload failed: {e}')
        return err('Upload failed. Please try again.', status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# ADMIN: CONFIRM PAYMENT
# ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_confirm_payment(request, order_id):
    """
    POST /api/payments/confirm/<order_id>/   (Admin only)

    Admin confirms that the customer's payment has been received and verified.

    Body:
    {
        "note": "optional admin note"
    }

    Transitions: payment_pending → paid
    Also confirms inventory reservations (moves reserved → sold).
    """
    order = Order.objects(id=order_id).first()
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    if order.payment.status == 'paid':
        return err(
            'Payment already confirmed for this order.',
            status_code=status.HTTP_409_CONFLICT,
            error='Conflict',
        )

    if order.status != 'payment_pending':
        return err(
            f'Order must be in payment_pending status to confirm. Current status: {order.status}',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    admin_note = request.data.get('note', '').strip()
    admin_id = str(request.user.id)

    # Use the reference number already stored on the order as the transaction ID
    transaction_id = order.payment.transaction_id or f'MANUAL-{order.order_number}'

    order = confirm_payment(
        order,
        transaction_id=transaction_id,
        provider='manual'
    )

    # Override the status update note with admin's note if provided
    if admin_note and order.status_history:
        order.status_history[-1].note = (
            f'Payment confirmed by admin. '
            + (f'Note: {admin_note}' if admin_note else '')
        )
        order.status_history[-1].actor = admin_id

    order.payment.confirmed_by = admin_id
    order.payment.confirmed_at = datetime.utcnow()
    order.save()

    logger.info(
        f'Payment CONFIRMED for order {order.order_number} '
        f'by admin {admin_id}. Ref: {transaction_id}'
    )

    return ok({
        'order_number': order.order_number,
        'status': order.status,
        'payment_status': order.payment.status,
        'confirmed_at': order.payment.confirmed_at.isoformat(),
    }, message=f'Payment confirmed for order {order.order_number}.')


# ─────────────────────────────────────────────────────────────────
# ADMIN: REJECT PAYMENT
# ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_reject_payment(request, order_id):
    """
    POST /api/payments/reject/<order_id>/   (Admin only)

    Admin rejects the submitted payment proof (e.g. wrong amount, fake screenshot).
    Order is moved back to pending so the customer can re-submit.

    Body:
    {
        "reason": "Amount received does not match order total."
    }
    """
    order = Order.objects(id=order_id).first()
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    if order.status != 'payment_pending':
        return err(
            f'Can only reject orders in payment_pending status. Current: {order.status}',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    reason = request.data.get('reason', 'Payment proof could not be verified.').strip()
    admin_id = str(request.user.id)

    order.payment.status = 'failed'
    order.payment.failure_reason = reason

    # Reset proof fields so customer must resubmit
    order.payment.transaction_id = ''
    order.payment.proof_url = ''
    order.payment.submitted_at = None

    order.update_status(
        'pending',
        note=f'Payment rejected by admin. Reason: {reason}. Customer must resubmit proof.',
        actor=admin_id
    )

    # Reset payment status back to pending so customer can resubmit
    order.payment.status = 'pending'
    order.save()

    logger.warning(
        f'Payment REJECTED for order {order.order_number} '
        f'by admin {admin_id}. Reason: {reason}'
    )

    return ok({
        'order_number': order.order_number,
        'status': order.status,
        'payment_status': order.payment.status,
        'rejection_reason': reason,
    }, message='Payment proof rejected. Customer will be notified to resubmit.')


# ─────────────────────────────────────────────────────────────────
# ADMIN: PROCESS REFUND
# ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_process_refund(request, order_id):
    """
    POST /api/payments/refund/<order_id>/   (Admin only)

    Marks an order as refunded after the admin has manually returned funds.
    Since payments are manual, the actual money transfer must happen outside the system.

    Body:
    {
        "refund_amount":    150.00,         (optional, defaults to grand_total)
        "refund_reference": "GCash ref",    (reference of the refund transfer)
        "reason":           "Customer request / item out of stock"
    }
    """
    order = Order.objects(id=order_id).first()
    if not order:
        return err('Order not found.', status_code=status.HTTP_404_NOT_FOUND, error='NotFound')

    if order.payment.status not in ('paid',):
        return err(
            'Can only refund orders that have been paid.',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    refund_amount = request.data.get('refund_amount')
    refund_reference = request.data.get('refund_reference', '').strip()
    reason = request.data.get('reason', 'Refund processed by admin.').strip()
    admin_id = str(request.user.id)

    # Default to full refund
    if refund_amount is None:
        refund_amount = float(order.grand_total)

    order.payment.status = 'refunded'
    order.payment.refunded_at = datetime.utcnow()
    order.payment.refund_amount = refund_amount
    order.payment.refund_reference = refund_reference

    order.update_status(
        'refunded',
        note=(
            f'Refund of {refund_amount} {order.currency} processed manually. '
            f'Ref: {refund_reference or "N/A"}. Reason: {reason}'
        ),
        actor=admin_id
    )
    order.save()

    logger.info(
        f'Refund processed for order {order.order_number} '
        f'by admin {admin_id}. Amount: {refund_amount} {order.currency}'
    )

    return ok({
        'order_number': order.order_number,
        'status': order.status,
        'payment_status': order.payment.status,
        'refund_amount': refund_amount,
        'currency': order.currency,
        'refunded_at': order.payment.refunded_at.isoformat(),
    }, message=f'Refund of {refund_amount} {order.currency} recorded successfully.')


# ─────────────────────────────────────────────────────────────────
# ADMIN: PENDING PAYMENTS QUEUE
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_pending_payments(request):
    """
    GET /api/payments/admin/pending/   (Admin only)

    Returns all orders with pending or payment_pending payment status.
    This includes orders awaiting payment submission and awaiting confirmation.
    """
    from apps.orders.serializers import OrderSerializer
    from config.pagination import StandardPagination

    pending = Order.objects(payment__status__in=['pending', 'payment_pending']).order_by('created_at')

    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(pending), request)

    data = []
    for order in page:
        data.append({
            'id': str(order.id),
            'order_number': order.order_number,
            'user_id': order.user_id,
            'grand_total': float(order.grand_total),
            'currency': order.currency,
            'payment_method': order.payment.method if order.payment else None,
            'payment_label': PAYMENT_INSTRUCTIONS.get(
                order.payment.method, {}
            ).get('label', 'Unknown') if order.payment else None,
            'reference_number': order.payment.transaction_id if order.payment else None,
            'proof_url': getattr(order.payment, 'proof_url', None) if order.payment else None,
            'submitted_at': getattr(order.payment, 'submitted_at', None),
            'customer_notes': order.customer_notes,
            'created_at': order.created_at.isoformat(),
        })

    return paginator.get_paginated_response(data)