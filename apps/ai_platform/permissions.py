from rest_framework.permissions import BasePermission


class IsAIRequestOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        owner_id = getattr(obj, 'user_id', None)
        if owner_id is None and hasattr(obj, 'request'):
            owner_id = obj.request.user_id
        return owner_id == request.user.id
