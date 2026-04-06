import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from presentation.dependency_config import get_manage_mappings_use_case


def create_mapping(request):
    if request.method == "POST":
        uc = get_manage_mappings_use_case()
        uc.create(
            connection_id=int(request.POST["connection_id"]),
            bank_account_iban=request.POST["bank_account_iban"],
            actual_budget_id=request.POST["actual_budget_id"],
            actual_account_id=request.POST["actual_account_id"],
            budget_encryption_password=request.POST.get("budget_encryption_password") or None,
        )
        return HttpResponse(status=204, headers={"HX-Refresh": "true"})
    return render(request, "partials/mapping_form.html", {"connection_id": request.GET.get("connection_id", "")})


@require_http_methods(["POST"])
def delete_mapping(request, mapping_id):
    uc = get_manage_mappings_use_case()
    uc.delete(mapping_id)
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


def list_budgets(request):
    uc = get_manage_mappings_use_case()
    budgets = uc.list_budgets()
    return JsonResponse([{"sync_id": b.sync_id, "name": b.name} for b in budgets], safe=False)


def list_accounts(request, budget_id):
    uc = get_manage_mappings_use_case()
    pw = request.GET.get("budget_encryption_password")
    accounts = uc.list_accounts_for_budget(budget_id, pw or None)
    return JsonResponse([{"id": a.id, "name": a.name} for a in accounts], safe=False)
