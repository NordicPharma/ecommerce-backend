# core/auth_signals.py
import logging
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed

logger = logging.getLogger("audit.access")

def _ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR"))

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    logger.info("login_success", extra={"props": {
        "user_id": user.id, "username": user.get_username(), "ip": _ip(request)
    }})

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    logger.info("logout", extra={"props": {
        "user_id": getattr(user, "id", None), "username": getattr(user, "get_username", lambda: None)(), "ip": _ip(request)
    }})

@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    logger.warning("login_failed", extra={"props": {
        "username": credentials.get("username"),
        "ip": _ip(request) if request else None
    }})