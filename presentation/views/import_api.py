import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from presentation.dependency_config import get_import_use_case, get_submit_tan_use_case
from presentation.forms import ImportForm, TANForm


logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def start_import(request):
    form = ImportForm(request.POST)
    if not form.is_valid():
        logger.warning("start_import invalid_form errors=%s", form.errors.get_json_data())
        return HttpResponse("Invalid form data", status=400)

    logger.debug(
        "start_import mapping_id=%s start_date=%s end_date=%s",
        form.cleaned_data["mapping_id"],
        form.cleaned_data["start_date"],
        form.cleaned_data.get("end_date"),
    )

    uc = get_import_use_case()
    result = uc.execute(
        mapping_id=form.cleaned_data["mapping_id"],
        start_date=form.cleaned_data["start_date"],
        end_date=form.cleaned_data.get("end_date"),
    )
    logger.debug("start_import result_type=%s", type(result).__name__)
    return render(request, "partials/import_result.html", {"result": result})


@require_http_methods(["POST"])
def submit_tan(request, session_id):
    form = TANForm(request.POST)
    if not form.is_valid():
        logger.warning("submit_tan invalid_form session_id=%s errors=%s", session_id, form.errors.get_json_data())
        return HttpResponse("Invalid TAN", status=400)

    logger.debug("submit_tan session_id=%s", session_id)

    uc = get_submit_tan_use_case()
    result = uc.execute(session_id=session_id, tan=form.cleaned_data["tan"])
    logger.debug("submit_tan result_type=%s", type(result).__name__)
    return render(request, "partials/import_result.html", {"result": result})
