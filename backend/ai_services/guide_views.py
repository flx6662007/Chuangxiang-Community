from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .guide import GuideInput, run_guide
from .views import ChatThrottle


@method_decorator(csrf_protect, name='dispatch')
class CompetitionGuideView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ChatThrottle]

    def state(self, request):
        saved = request.session.get('competition_guide', {})
        owner = request.user.pk if request.user.is_authenticated else None
        return saved.get('state', {}) if saved.get('owner') == owner else {}

    def get(self, request):
        _, result = run_guide({'action': 'restore'}, self.state(request), user=request.user)
        return Response(result)

    def post(self, request):
        serializer = GuideInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        state, result = run_guide(serializer.validated_data, self.state(request), user=request.user)
        request.session['competition_guide'] = {'owner': request.user.pk if request.user.is_authenticated else None, 'state': state}
        request.session.set_expiry(60 * 60 * 24 * 7)
        return Response(result)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response
