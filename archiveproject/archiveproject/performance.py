import logging
from time import perf_counter

from django.conf import settings


logger = logging.getLogger('archiveproject.performance')


class RequestTimingMiddleware:
    """Expose application timing and log requests that need investigation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = perf_counter()
        response = self.get_response(request)
        duration_ms = (perf_counter() - started_at) * 1000
        response['Server-Timing'] = f'app;dur={duration_ms:.1f}'
        if duration_ms >= settings.SLOW_REQUEST_MS:
            logger.warning(
                'Slow request method=%s path=%s status=%s duration_ms=%.1f',
                request.method,
                request.path,
                response.status_code,
                duration_ms,
            )
        return response
