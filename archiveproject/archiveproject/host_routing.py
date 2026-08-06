from django.conf import settings
from django.shortcuts import redirect


def request_hostname(request):
    return request.get_host().split(':', 1)[0].lower()


class KoperasiHostMiddleware:
    """Use an isolated URL configuration on the Koperasi subdomain."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request_hostname(request) in settings.KOPERASI_HOSTS:
            request.urlconf = 'koperasi.host_urls'
        return self.get_response(request)


class SystemBoundaryMiddleware:
    """Prevent Koperasi-only users from entering the archive application."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        hostname = request_hostname(request)
        is_koperasi_host = hostname in settings.KOPERASI_HOSTS

        if (
            getattr(user, "is_authenticated", False)
            and not user.is_superuser
            and user.role == "akuntan"
            and not is_koperasi_host
            and request.path != "/accounts/logout/"
        ):
            requested_host = request.get_host()
            if hostname in {"localhost", "archive.localhost"}:
                port_suffix = (
                    f":{requested_host.rsplit(':', 1)[1]}"
                    if ":" in requested_host
                    else ""
                )
                return redirect(f"http://koperasi.localhost{port_suffix}/")
            return redirect(settings.KOPERASI_BASE_URL)

        return self.get_response(request)


class LandingHostMiddleware:
    """Keep the public company domain separate from archive application URLs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hostname = request_hostname(request)
        is_landing_host = hostname in settings.LANDING_HOSTS
        is_public_path = (
            request.path == '/'
            or request.path.startswith(f"/{settings.STATIC_URL.lstrip('/')}")
        )
        if is_landing_host and not is_public_path:
            return redirect('/')
        return self.get_response(request)
