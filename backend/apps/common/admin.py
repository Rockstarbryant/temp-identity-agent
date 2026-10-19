"""Shared admin helpers."""
from django.contrib import admin


class ReadOnlyAdmin(admin.ModelAdmin):
    """
    Admin page that only lets staff look, never edit or add.

    Nearly everything in this project is written by the app or the agent, so hand edits in
    the admin would only corrupt state. List the encrypted / hashed columns in `secret_fields`:
    they are never rendered, so even a superuser cannot read them here.
    """

    secret_fields: tuple[str, ...] = ()

    def get_exclude(self, request, obj=None):
        return list(self.secret_fields)

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields if f.name not in self.secret_fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
