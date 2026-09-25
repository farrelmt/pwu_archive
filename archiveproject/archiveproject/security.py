import secrets

from django.utils.cache import patch_cache_control


class SecurityHeadersMiddleware:
    """Attach a per-response CSP nonce and modern browser security policy."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(24)
        response = self.get_response(request)
        nonce = request.csp_nonce
        hostname = request.get_host().split(":", 1)[0].lower()
        policy = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        # Production is HTTPS-only, but local Docker system links use HTTP
        # subdomains such as archive.localhost:8000. Upgrading those links to
        # HTTPS makes browsers silently reject their navigation.
        if hostname != "localhost" and not hostname.endswith(".localhost"):
            policy += "; upgrade-insecure-requests"
        response["Content-Security-Policy"] = policy
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response["Cross-Origin-Resource-Policy"] = "same-origin"
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            patch_cache_control(
                response,
                private=True,
                no_cache=True,
                no_store=True,
                must_revalidate=True,
                max_age=0,
            )
        return response
