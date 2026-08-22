import json
import logging

from django.conf import settings
from django.http import HttpRequest
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from polar.v2026_04.webhooks import PolarWebhookError
from polar.v2026_04.webhooks import PolarWebhookUnknownTypeError
from polar.v2026_04.webhooks import PolarWebhookVerificationError
from polar.v2026_04.webhooks import validate_event

from apps.billing.services import process_webhook_event

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class WebhookView(View):
    """Receive Polar webhook deliveries; verify and record every one, apply subscription events idempotently."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest) -> HttpResponse:
        headers = {
            "webhook-id": request.headers.get("webhook-id", ""),
            "webhook-timestamp": request.headers.get("webhook-timestamp", ""),
            "webhook-signature": request.headers.get("webhook-signature", ""),
        }

        try:
            event = validate_event(request.body, headers, settings.POLAR_WEBHOOK_SECRET)
        except PolarWebhookVerificationError:
            return HttpResponse(status=403)
        except PolarWebhookUnknownTypeError:
            return HttpResponse(status=200)
        except PolarWebhookError:
            return HttpResponse(status=400)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        try:
            process_webhook_event(
                event_id=headers["webhook-id"],
                event_type=event.type,
                payload=payload,
                data=event.data,
            )
        except Exception:
            logger.exception("Failed to process webhook event %s", headers["webhook-id"])
            return HttpResponse(status=500)

        return HttpResponse(status=200)
