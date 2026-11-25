import json
import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from django.conf import settings

from .metrics import request_duration, requests_total

logger = logging.getLogger("library.requests")


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        request_id = uuid4().hex
        response = self.get_response(request)
        response["X-Request-ID"] = request_id

        status = response.status_code
        if status >= 500:
            level = logging.ERROR
        elif status >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO

        match = request.resolver_match
        route = "/" + match.route.lstrip("/") if match and match.route is not None else "unresolved"
        if settings.METRICS_ENABLED and route != "/metrics/":
            requests_total.labels(route, f"{status // 100}xx").inc()
            request_duration.labels(route).observe(perf_counter() - started)

        logger.log(
            level,
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": logging.getLevelName(level),
                    "event": "http_request",
                    "route": route,
                    "status": status,
                    "request_id": request_id,
                }
            ),
        )
        return response
