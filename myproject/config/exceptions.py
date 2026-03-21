import logging

from rest_framework import status
from rest_framework.exceptions import ValidationError, APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


ERROR_LABELS = {
    status.HTTP_400_BAD_REQUEST: 'Bad Request',
    status.HTTP_401_UNAUTHORIZED: 'Unauthorized',
    status.HTTP_403_FORBIDDEN: 'Forbidden',
    status.HTTP_404_NOT_FOUND: 'Not Found',
    status.HTTP_409_CONFLICT: 'Conflict',
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: 'Payload Too Large',
    status.HTTP_422_UNPROCESSABLE_ENTITY: 'Validation Error',
    status.HTTP_500_INTERNAL_SERVER_ERROR: 'Internal Server Error',
}


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Conflict.'
    default_code = 'conflict'


class PayloadTooLargeError(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = 'Uploaded payload is too large.'
    default_code = 'payload_too_large'


def success_response(data=None, message: str = '', status_code: int = status.HTTP_200_OK):
    """
    Standard success wrapper used across the API.
    """
    return Response(
        {
            'success': True,
            'status_code': status_code,
            'message': message,
            'data': data or {},
        },
        status=status_code,
    )


def error_response(
    error: str,
    message: str = '',
    *,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    errors: dict | None = None,
):
    """
    Standard error wrapper used for manually constructed errors.
    """
    label = error or ERROR_LABELS.get(status_code, 'Error')
    return Response(
        {
            'success': False,
            'status_code': status_code,
            'error': label,
            'message': message or label,
            'errors': errors or {},
        },
        status=status_code,
    )


def _get_error_label(status_code: int) -> str:
    return ERROR_LABELS.get(status_code, 'Error')


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns clear, consistent error responses.

    This is applied to:
    - DRF / serializer validation errors
    - Authentication / permission failures
    - Explicit APIException subclasses (e.g. ConflictError, PayloadTooLargeError)
    - Any other unhandled exceptions (mapped to HTTP 500)
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Normalize validation errors to 422 instead of 400
        if isinstance(exc, ValidationError) and response.status_code == status.HTTP_400_BAD_REQUEST:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

        status_code = response.status_code
        error_data = {
            'success': False,
            'status_code': status_code,
            'error': _get_error_label(status_code),
            'message': '',
            'errors': {},
        }

        if isinstance(response.data, dict):
            if 'detail' in response.data:
                error_data['message'] = str(response.data['detail'])
            else:
                error_data['message'] = 'Validation error' if isinstance(exc, ValidationError) else ''
                error_data['errors'] = response.data
        elif isinstance(response.data, list):
            error_data['message'] = 'Validation error'
            error_data['errors'] = {'non_field_errors': response.data}
        else:
            error_data['message'] = str(response.data)

        if not error_data['message']:
            # Fallback to exception text or generic label
            error_data['message'] = str(exc) or error_data['error']

        response.data = error_data
        return response

    # Unhandled exception — log and return a generic 500 response
    logger.exception('Unhandled exception', exc_info=exc)
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return Response(
        {
            'success': False,
            'status_code': status_code,
            'error': _get_error_label(status_code),
            'message': 'An internal server error occurred.',
            'errors': {},
        },
        status=status_code,
    )