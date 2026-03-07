from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """Admin can write; everyone can read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsOwnerOrAdmin(BasePermission):
    """Only resource owner or admin can access."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        owner_id = getattr(obj, 'user_id', None) or getattr(obj, 'user', None)
        return str(owner_id) == str(request.user.id)


class IsVerifiedUser(BasePermission):
    """User must be verified/active."""
    message = 'Account not verified.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_verified and request.user.is_active)