from django.conf import settings

from application.use_cases.import_transactions import ImportTransactionsUseCase
from application.use_cases.manage_connections import ManageConnectionsUseCase
from application.use_cases.manage_mappings import ManageMappingsUseCase
from application.use_cases.submit_tan import SubmitTANUseCase
from application.use_cases.sync_all import SyncAllUseCase
from infrastructure.actual.client import ActualClientAdapter
from infrastructure.crypto.fernet_store import FernetCredentialStore
from infrastructure.fints.client import FinTSClientAdapter
from infrastructure.persistence.repositories import (
    ConnectionRepository,
    MappingRepository,
    SessionRepository,
)
from infrastructure.webhook.notifier import WebhookNotifier


def get_credential_store() -> FernetCredentialStore:
    return FernetCredentialStore()


def get_fints_client() -> FinTSClientAdapter:
    return FinTSClientAdapter(settings.FINTS_PRODUCT_ID, settings.FINTS_PRODUCT_VERSION)


def get_actual_client() -> ActualClientAdapter:
    return ActualClientAdapter(settings.ACTUAL_API_URL, settings.ACTUAL_API_KEY)


def get_connection_repo() -> ConnectionRepository:
    return ConnectionRepository()


def get_mapping_repo() -> MappingRepository:
    return MappingRepository()


def get_session_repo() -> SessionRepository:
    return SessionRepository()


def get_webhook_notifier() -> WebhookNotifier:
    return WebhookNotifier()


def get_import_use_case() -> ImportTransactionsUseCase:
    return ImportTransactionsUseCase(
        fints_port=get_fints_client(),
        actual_port=get_actual_client(),
        credential_store=get_credential_store(),
        session_repo=get_session_repo(),
        mapping_repo=get_mapping_repo(),
        connection_repo=get_connection_repo(),
        notification_port=get_webhook_notifier(),
        base_url=getattr(settings, "BASE_URL", "http://localhost:8000"),
    )


def get_submit_tan_use_case() -> SubmitTANUseCase:
    return SubmitTANUseCase(
        fints_port=get_fints_client(),
        actual_port=get_actual_client(),
        credential_store=get_credential_store(),
        session_repo=get_session_repo(),
        mapping_repo=get_mapping_repo(),
        connection_repo=get_connection_repo(),
        tan_session_timeout_minutes=settings.TAN_SESSION_TIMEOUT_MINUTES,
    )


def get_manage_connections_use_case() -> ManageConnectionsUseCase:
    return ManageConnectionsUseCase(
        connection_repo=get_connection_repo(),
        credential_store=get_credential_store(),
        fints_port=get_fints_client(),
    )


def get_manage_mappings_use_case() -> ManageMappingsUseCase:
    return ManageMappingsUseCase(
        mapping_repo=get_mapping_repo(),
        actual_port=get_actual_client(),
        credential_store=get_credential_store(),
    )


def get_sync_all_use_case() -> SyncAllUseCase:
    return SyncAllUseCase(
        import_use_case=get_import_use_case(),
    )
