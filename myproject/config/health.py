from django.urls import path
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import mongoengine


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    checks = {'api': 'ok', 'database': 'unknown'}
    try:
        mongoengine.connection.get_db()
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {str(e)}'

    all_ok = all(v == 'ok' for v in checks.values())
    return Response({'status': 'healthy' if all_ok else 'degraded', 'checks': checks},
                    status=200 if all_ok else 503)


urlpatterns = [path('', health_check)]