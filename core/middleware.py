# core/middleware.py
import logging, time
from ipaddress import ip_address

logger = logging.getLogger("audit.access")

SENSITIVE_QUERY_KEYS = {"password", "token", "secret", "csrfmiddlewaretoken"}

def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    # valida IP por seguridad
    try:
        ip_address(ip)
    except Exception:
        ip = None
    return ip

def _redact_query(d):
    out = {}
    for k, v in d.items():
        out[k] = "***redacted***" if k.lower() in SENSITIVE_QUERY_KEYS else v
    return out

class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        dur_ms = int((time.monotonic() - start) * 1000)

        # opcional: salta estáticos/healthchecks
        if request.path.startswith(("/static/", "/media/")):
            return response

        user = getattr(request, "user", None)
        username = user.get_username() if getattr(user, "is_authenticated", False) else None
        payload = {
            "method": request.method,
            "path": request.path,
            "query": _redact_query(request.GET.dict()),
            "status": response.status_code,
            "ms": dur_ms,
            "ip": _client_ip(request),
            "ua": request.META.get("HTTP_USER_AGENT"),
            "user_id": getattr(user, "id", None),
            "username": username,
            "session": getattr(request, "session", None) and request.session.session_key,
        }
        logger.info("http_access", extra={"props": payload})
        return response