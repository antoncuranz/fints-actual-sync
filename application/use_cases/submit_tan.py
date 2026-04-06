from datetime import datetime, timedelta

from django.conf import settings

from application.dto import ImportResultDTO, TANRequiredDTO
from domain.entities import ImportStatus
from domain.exceptions import InvalidSessionState, TanSessionExpiredError
from domain.ports import (
    ActualClientPort,
    ConnectionRepository,
    CredentialStore,
    FinTSClientPort,
    MappingRepository,
    SessionRepository,
    TANChallenge,
)


class SubmitTANUseCase:
    def __init__(
        self,
        fints_port: FinTSClientPort,
        actual_port: ActualClientPort,
        credential_store: CredentialStore,
        session_repo: SessionRepository,
        mapping_repo: MappingRepository,
        connection_repo: ConnectionRepository,
    ):
        self._fints = fints_port
        self._actual = actual_port
        self._creds = credential_store
        self._sessions = session_repo
        self._mappings = mapping_repo
        self._connections = connection_repo

    def execute(self, session_id: int, tan: str) -> ImportResultDTO | TANRequiredDTO:
        session = self._sessions.get_by_id(session_id)

        if session.status != ImportStatus.TAN_REQUIRED:
            raise InvalidSessionState(f"Session {session_id} is not waiting for TAN")

        timeout = timedelta(minutes=settings.TAN_SESSION_TIMEOUT_MINUTES)
        if datetime.now() - session.started_at > timeout:
            self._sessions.delete(session.id)
            raise TanSessionExpiredError(f"Session {session_id} has expired")

        connection = self._connections.get_by_id(session.connection_id)
        mapping = self._mappings.get_by_id(session.mapping_id)

        result = self._fints.submit_tan(
            connection, session.client_state_blob, session.dialog_state_blob, session.tan_state_blob, tan
        )

        if isinstance(result, TANChallenge):
            session.challenge_text = result.challenge_text
            session.client_state_blob = result.client_state_blob
            session.dialog_state_blob = result.dialog_state_blob
            session.tan_state_blob = result.tan_state_blob
            self._sessions.save(session)
            return TANRequiredDTO(session_id=session.id, challenge_text=result.challenge_text)

        self._sessions.delete(session.id)
        return self._export_to_actual(result, mapping)

    def _export_to_actual(self, transactions, mapping) -> ImportResultDTO:
        for tx in transactions:
            tx.account = mapping.actual_account_id
        budget_pw = mapping.budget_encryption_password
        result = self._actual.import_transactions(mapping.actual_budget_id, mapping.actual_account_id, transactions, budget_pw)
        return ImportResultDTO(status="completed", imported=len(result.added), updated=len(result.updated))
