import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent error responses.
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            'success': False,
            'status_code': response.status_code,
            'errors': {},
        }

        if isinstance(response.data, dict):
            if 'detail' in response.data:
                error_data['message'] = str(response.data['detail'])
            else:
                error_data['message'] = 'Validation error'
                error_data['errors'] = response.data
        elif isinstance(response.data, list):
            error_data['message'] = 'Validation error'
            error_data['errors'] = {'non_field_errors': response.data}
        else:
            error_data['message'] = str(response.data)

        response.data = error_data
    else:
        # Unhandled exception
        logger.exception(f'Unhandled exception: {exc}', exc_info=exc)
        response = Response(
            {
                'success': False,
                'status_code': 500,
                'message': 'An internal server error occurred.',
                'errors': {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response