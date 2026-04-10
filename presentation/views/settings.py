import json
import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from infrastructure.persistence.models import WebhookConfigModel
from infrastructure.webhook.notifier import WebhookNotifier
from presentation.forms import WebhookConfigForm

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def webhook_settings(request):
    config = WebhookConfigModel.objects.first()
    initial = {}
    if config:
        initial = {
            "url": config.url,
            "body_template": config.body_template,
            "method": config.method,
            "headers": json.dumps(config.headers) if config.headers else "",
            "enabled": config.enabled,
        }
    form = WebhookConfigForm(initial=initial)
    return render(request, "settings/webhook.html", {"form": form, "config": config})


@require_http_methods(["POST"])
def webhook_settings_save(request):
    form = WebhookConfigForm(request.POST)
    if not form.is_valid():
        return render(request, "settings/webhook.html", {"form": form})

    headers_str = form.cleaned_data.get("headers") or "{}"
    try:
        headers = json.loads(headers_str)
    except json.JSONDecodeError:
        form.add_error("headers", "Invalid JSON")
        return render(request, "settings/webhook.html", {"form": form})

    config = WebhookConfigModel.objects.first()
    if config:
        config.url = form.cleaned_data["url"]
        config.body_template = form.cleaned_data["body_template"]
        config.method = form.cleaned_data["method"]
        config.headers = headers
        config.enabled = form.cleaned_data["enabled"]
        config.save()
    else:
        WebhookConfigModel.objects.create(
            url=form.cleaned_data["url"],
            body_template=form.cleaned_data["body_template"],
            method=form.cleaned_data["method"],
            headers=headers,
            enabled=form.cleaned_data["enabled"],
        )

    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


@require_http_methods(["POST"])
def webhook_test(request):
    notifier = WebhookNotifier()
    notifier.notify_tan_required(
        session_id=0,
        challenge_text="[TEST] This is a test TAN notification",
        tan_submit_url="http://localhost:8000/",
    )
    return HttpResponse("Test webhook sent. Check logs for delivery status.")
