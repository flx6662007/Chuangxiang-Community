"""Infrastructure endpoints; business endpoints belong to their own apps."""

from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Confirm HTTP service availability without querying business tables."""

    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return Response({'status': 'ok', 'service': 'chuangxiang-backend'})
