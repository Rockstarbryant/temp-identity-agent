from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Object-level permission restricting access to the resource's owner.

    Every model this is used against (RegistrationJob, TemporaryAccount,
    TemporaryIdentity, ...) must expose a `.user` attribute (directly or
    via a related object) that this checks against `request.user`.
    """

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        if owner is None and hasattr(obj, "job"):
            owner = getattr(obj.job, "user", None)
        if owner is None and hasattr(obj, "identity"):
            owner = getattr(obj.identity, "user", None)
        return owner is not None and owner == request.user
