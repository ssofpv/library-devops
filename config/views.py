import re

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse(
            {"status": "error", "database": "unavailable"},
            status=503,
        )

    return JsonResponse({"status": "ok"})


@require_GET
def version(request):
    try:
        revision = (settings.BASE_DIR / "build-version.txt").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        revision = ""

    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        return JsonResponse({"error": "version unavailable"}, status=503)

    response = JsonResponse({"version": revision})
    response["Cache-Control"] = "no-store"
    return response
