# catalog/permissions.py

from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """
    Allows access only to admin users (is_staff = True).
    """
    def has_permission(self, request, view):
        print("i have touched the auth permission class",request.user.is_staff)
        return bool(request.user and request.user.is_staff)