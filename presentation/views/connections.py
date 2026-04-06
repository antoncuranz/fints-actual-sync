import json

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from presentation.dependency_config import get_manage_connections_use_case
from presentation.forms import ConnectionForm


def create_connection(request):
    if request.method == "POST":
        form = ConnectionForm(request.POST)
        if form.is_valid():
            uc = get_manage_connections_use_case()
            uc.create(
                name=form.cleaned_data["name"],
                blz=form.cleaned_data["blz"],
                url=form.cleaned_data["url"],
                user_id=form.cleaned_data["user_id"],
                customer_id=form.cleaned_data.get("customer_id") or None,
                pin=form.cleaned_data["pin"],
            )
            return HttpResponse(status=204, headers={"HX-Refresh": "true"})
    else:
        form = ConnectionForm()
    return render(request, "partials/connection_form.html", {"form": form})


@require_http_methods(["POST"])
def delete_connection(request, connection_id):
    uc = get_manage_connections_use_case()
    uc.delete(connection_id)
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


@require_http_methods(["POST"])
def discover_accounts(request, connection_id):
    uc = get_manage_connections_use_case()
    result = uc.discover_accounts(connection_id)
    if isinstance(result, list):
        return HttpResponse(json.dumps([{"iban": a.iban, "owner_name": a.owner_name} for a in result]), content_type="application/json")
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})
