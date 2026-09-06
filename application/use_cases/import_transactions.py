import logging
from datetime import date, datetime

from application.dto import ImportResultDTO, TANRequiredDTO
from application.use_cases._export import export_to_actual
from domain.entities import ImportSession, ImportStatus
from domain.ports import (
    ActualClientPort,
    ConnectionRepository,
    CredentialStore,
    FinTSClientPort,
    MappingRepository,
    NotificationPort,
    SessionRepository,
    TANChallenge,
)


logger = logging.getLogger(__name__)


class ImportTransactionsUseCase:
    def __init__(
        self,
        fints_port: FinTSClientPort,
        actual_port: ActualClientPort,
        credential_store: CredentialStore,
        session_repo: SessionRepository,
        mapping_repo: MappingRepository,
        connection_repo: ConnectionRepository,
        notification_port: NotificationPort | None = None,
        base_url: str = "",
    ):
        self._fints = fints_port
        self._actual = actual_port
        self._creds = credential_store
        self._sessions = session_repo
        self._mappings = mapping_repo
        self._connections = connection_repo
        self._notification = notification_port
        self._base_url = base_url.rstrip("/")

    def execute(self, mapping_id: int, start_date: date, end_date=None) -> ImportResultDTO | TANRequiredDTO:
        mapping = self._mappings.get_by_id(mapping_id)
        connection = self._connections.get_by_id(mapping.connection_id)

        logger.debug(
            "import_execute mapping_id=%s connection_id=%s iban_suffix=%s start_date=%s end_date=%s actual_budget_id=%s actual_account_id=%s",
            mapping.id,
            connection.id,
            mapping.bank_account_iban[-4:],
            start_date,
            end_date,
            mapping.actual_budget_id,
            mapping.actual_account_id,
        )

        result = self._fints.fetch_transactions(connection, mapping.bank_account_iban, start_date, end_date)

        logger.debug("import_execute fetch_result_type=%s", type(result).__name__)

        if isinstance(result, TANChallenge):
            session = self._sessions.save(ImportSession(
                connection_id=connection.id,
                mapping_id=mapping.id,
                status=ImportStatus.TAN_REQUIRED,
                started_at=datetime.now(),
                challenge_text=result.challenge_text,
                client_state_blob=result.client_state_blob,
                dialog_state_blob=result.dialog_state_blob,
                tan_state_blob=result.tan_state_blob,
                decoupled=result.decoupled,
                resume_transaction_fetch=result.resume_transaction_fetch,
                start_date=start_date,
                end_date=end_date,
            ))
            logger.debug("import_execute tan_required session_id=%s", session.id)
            if self._notification:
                self._notification.notify_tan_required(
                    session_id=session.id,
                    challenge_text=result.challenge_text,
                    tan_submit_url=f"{self._base_url}/" if self._base_url else "",
                )
            return TANRequiredDTO(session_id=session.id, challenge_text=result.challenge_text, decoupled=result.decoupled)

        logger.debug("import_execute transaction_count=%s", len(result))
        return export_to_actual(result, mapping, self._actual)
