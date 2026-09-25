from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from urllib.parse import urlencode


def request_hostname(request):
    return request.get_host().split(':', 1)[0].lower()


def portal_base_url(request):
    hostname = request_hostname(request)
    if hostname == "localhost" or hostname.endswith(".localhost"):
        requested_host = request.get_host()
        port_suffix = (
            f":{requested_host.rsplit(':', 1)[1]}"
            if ":" in requested_host
            else ""
        )
        return f"http://localhost{port_suffix}"
    return settings.PORTAL_BASE_URL


class SharedDomainSessionMiddleware(SessionMiddleware):
    """Share the authenticated session across PWU system subdomains."""

    def process_response(self, request, response):
        response = super().process_response(request, response)
        session_cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
        if session_cookie is not None:
            hostname = request_hostname(request)
            if hostname == "localhost" or hostname.endswith(".localhost"):
                # Browsers reject/ignore parent-domain cookies for localhost.
                # Keep each local session host-only; the signed system handoff
                # establishes the corresponding subdomain session.
                session_cookie["domain"] = ""
            elif hostname == "pwujatim.site" or hostname.endswith(".pwujatim.site"):
                session_cookie["domain"] = ".pwujatim.site"
        return response


class KoperasiHostMiddleware:
    """Use an isolated URL configuration on the Koperasi subdomain."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request_hostname(request) in settings.KOPERASI_HOSTS:
            request.urlconf = 'koperasi.host_urls'
        return self.get_response(request)


class RiskHostMiddleware:
    """Use an isolated URL configuration on the Risk Management subdomain."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request_hostname(request) in settings.RISK_HOSTS:
            request.urlconf = 'risk_management.host_urls'
        return self.get_response(request)


class InventoryHostMiddleware:
    """Use an isolated URL configuration on the Inventory subdomain."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request_hostname(request) in settings.INVENTORY_HOSTS:
            request.urlconf = 'inventory.host_urls'
        return self.get_response(request)


class SystemBoundaryMiddleware:
    """Keep every system behind authentication and an explicit active role."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hostname = request_hostname(request)
        system_hosts = (
            settings.KOPERASI_HOSTS | settings.RISK_HOSTS
            | settings.INVENTORY_HOSTS | settings.ARCHIVE_HOSTS
        )
        is_asset = (
            request.path.startswith(f"/{settings.STATIC_URL.lstrip('/')}")
            or request.path.startswith(settings.MEDIA_URL)
        )
        is_handoff = request.path == "/accounts/handoff/"
        if (
            hostname in system_hosts
            and not request.user.is_authenticated
            and not is_asset
            and not is_handoff
        ):
            query = urlencode({"next": request.build_absolute_uri()})
            return redirect(f"{portal_base_url(request)}/accounts/login/?{query}")
        if (
            hostname in system_hosts
            and request.user.is_authenticated
            and not is_asset
            and not is_handoff
        ):
            from accounts.access import has_system_access

            if hostname in settings.KOPERASI_HOSTS:
                system = "koperasi"
            elif hostname in settings.RISK_HOSTS:
                system = "risk"
            elif hostname in settings.INVENTORY_HOSTS:
                system = "inventory"
            else:
                system = "archive"
            if not has_system_access(request.user, system):
                raise PermissionDenied("Akun Anda tidak memiliki akses ke sistem ini.")
        return self.get_response(request)


class LandingHostMiddleware:
    """Keep the main portal limited to login, logout, and system selection."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hostname = request_hostname(request)
        is_landing_host = hostname in settings.LANDING_HOSTS
        is_portal_path = (
            request.path == '/'
            or request.path.startswith('/accounts/login/')
            or request.path.startswith('/accounts/logout/')
            or request.path.startswith('/accounts/system/')
            or request.path == '/member'
            or request.path.startswith('/member/')
            or request.path == '/settings'
            or request.path.startswith('/settings/')
            or request.path.startswith(f"/{settings.STATIC_URL.lstrip('/')}")
        )
        if is_landing_host and not is_portal_path:
            return redirect('/')
        return self.get_response(request)
