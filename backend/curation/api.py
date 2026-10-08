"""Shared HTTP behavior for knowledge, resource and catalog reads."""

from rest_framework.permissions import AllowAny

from .api_permissions import library_preview


class LibraryReadMixin:
    permission_classes = (AllowAny,)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.preview = library_preview(request)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response
