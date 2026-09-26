from django.utils import timezone
from rest_framework.response import Response
from teams.views import BusinessView
from teams.serializers import StrictSerializer
from .models import Notification


def output(note, user=None):
    event = note.event
    target = next(({'type': key, 'id': getattr(event, key + '_id')} for key in
        ['recruitment', 'application', 'departure_request', 'dissolution_request', 'admin_action'] if getattr(event, key + '_id')), None)
    return {'id': note.pk, 'title': note.title, 'body': note.body, 'created_at': note.created_at,
            'read_at': note.read_at, 'kind': event.kind, 'payload': event.payload, 'target': target}


class NotificationListView(BusinessView):
    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user).select_related('event').order_by('-id')
        if request.query_params.get('unread') in ['true', '1']:
            qs = qs.filter(read_at__isnull=True)
        return self.page(qs, output)


class NotificationReadView(BusinessView):
    def post(self, request, pk):
        from django.db import transaction
        self.read_input(StrictSerializer)
        with transaction.atomic():
            note = Notification.objects.select_for_update().select_related('event').get(pk=pk, recipient=request.user)
            if note.read_at is None:
                note.read_at = timezone.now()
                note.full_clean()
                note.save(update_fields=['read_at'])
        return Response(output(note))
