import json
import logging
from string import Template

import httpx

from infrastructure.persistence.models import WebhookConfigModel

logger = logging.getLogger(__name__)

DEFAULT_BODY_TEMPLATE = '{"event": "$event", "session_id": "$session_id", "challenge_text": "$challenge_text", "tan_submit_url": "$tan_submit_url"}'


class WebhookNotifier:
    def notify_tan_required(self, session_id: int, challenge_text: str, tan_submit_url: str) -> None:
        config = WebhookConfigModel.objects.first()
        if not config or not config.enabled or not config.url:
            return

        variables = {
            "event": "tan_required",
            "session_id": str(session_id),
            "challenge_text": challenge_text,
            "tan_submit_url": tan_submit_url,
        }

        try:
            template = Template(config.body_template or DEFAULT_BODY_TEMPLATE)
            body = template.safe_substitute(variables)
        except Exception:
            logger.exception("Failed to render webhook body template")
            return

        headers = {"Content-Type": "application/json"}
        if isinstance(config.headers, dict):
            headers.update(config.headers)

        try:
            response = httpx.request(
                method=config.method,
                url=config.url,
                content=body,
                headers=headers,
                timeout=5.0,
            )
            response.raise_for_status()
            logger.info("Webhook sent to %s, status=%s", config.url, response.status_code)
        except Exception:
            logger.warning("Webhook delivery failed for url=%s", config.url, exc_info=True)
