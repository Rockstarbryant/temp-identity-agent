"""
Shared, unauthenticated utility views.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """
    Lightweight liveness probe used by Docker HEALTHCHECK, Render, and
    load balancers. Does not touch the database or Redis.
    """
    return JsonResponse({"status": "ok"})
