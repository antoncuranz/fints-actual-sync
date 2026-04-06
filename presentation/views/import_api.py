from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from presentation.dependency_config import get_import_use_case, get_submit_tan_use_case
from presentation.forms import ImportForm, TANForm


@require_http_methods(["POST"])
def start_import(request):
    form = ImportForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Invalid form data", status=400)

    uc = get_import_use_case()
    result = uc.execute(
        mapping_id=form.cleaned_data["mapping_id"],
        start_date=form.cleaned_data["start_date"],
        end_date=form.cleaned_data.get("end_date"),
    )
    return render(request, "partials/import_result.html", {"result": result})


@require_http_methods(["POST"])
def submit_tan(request, session_id):
    form = TANForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Invalid TAN", status=400)

    uc = get_submit_tan_use_case()
    result = uc.execute(session_id=session_id, tan=form.cleaned_data["tan"])
    return render(request, "partials/import_result.html", {"result": result})
