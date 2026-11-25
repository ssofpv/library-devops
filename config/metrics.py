import os

from django.conf import settings
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)
from prometheus_client.core import GaugeMetricFamily

from inventory.models import Copy

request_registry = CollectorRegistry()
requests_total = Counter(
    "library_http_requests_total",
    "HTTP responses by route and status class.",
    ("route", "status_class"),
    registry=request_registry,
)
request_duration = Histogram(
    "library_http_request_duration_seconds",
    "Time spent processing HTTP requests.",
    ("route",),
    registry=request_registry,
)


class LibraryStateCollector:
    def collect(self):
        try:
            available = Copy.objects.filter(status=Copy.Status.AVAILABLE).count()
        except DatabaseError:
            yield GaugeMetricFamily("library_app_ready", "Can read the library database.", value=0)
            return

        yield GaugeMetricFamily("library_app_ready", "Can read the library database.", value=1)
        yield GaugeMetricFamily(
            "library_available_copies", "Available library copies.", value=available
        )


@require_GET
def metrics(request):
    if not settings.METRICS_ENABLED:
        raise Http404

    http_registry = request_registry
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        http_registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(http_registry)

    state_registry = CollectorRegistry()
    state_registry.register(LibraryStateCollector())
    response = HttpResponse(
        generate_latest(http_registry) + generate_latest(state_registry),
        content_type=CONTENT_TYPE_LATEST,
    )
    response["Cache-Control"] = "no-store"
    return response
