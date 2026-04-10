from django.urls import path

from .connections import create_connection, delete_connection, discover_accounts
from .dashboard import dashboard
from .import_api import start_import, submit_tan, sync_all
from .mappings import create_mapping, delete_mapping, list_accounts, list_budgets
from .settings import webhook_settings, webhook_settings_save, webhook_test

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("connections/new/", create_connection, name="create_connection"),
    path("connections/<int:connection_id>/delete/", delete_connection, name="delete_connection"),
    path("connections/<int:connection_id>/discover-accounts/", discover_accounts, name="discover_accounts"),
    path("mappings/new/", create_mapping, name="create_mapping"),
    path("mappings/<int:mapping_id>/delete/", delete_mapping, name="delete_mapping"),
    path("api/budgets/", list_budgets, name="list_budgets"),
    path("api/budgets/<str:budget_id>/accounts/", list_accounts, name="list_accounts"),
    path("api/imports/", start_import, name="start_import"),
    path("internal/api/imports/sync-all/", sync_all, name="sync_all"),
    path("api/imports/<int:session_id>/submit-tan/", submit_tan, name="submit_tan"),
    path("settings/webhook/", webhook_settings, name="webhook_settings"),
    path("settings/webhook/save/", webhook_settings_save, name="webhook_settings_save"),
    path("settings/webhook/test/", webhook_test, name="webhook_test"),
]
