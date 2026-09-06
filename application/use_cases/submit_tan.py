from datetime import timedelta

from django.utils import timezone

from application.dto import ImportResultDTO, TANRequiredDTO
from application.use_cases._export import export_to_actual
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
        tan_session_timeout_minutes: int,
    ):
        self._fints = fints_port
        self._actual = actual_port
        self._creds = credential_store
        self._sessions = session_repo
        self._mappings = mapping_repo
        self._connections = connection_repo
        self._timeout_minutes = tan_session_timeout_minutes

    def execute(self, session_id: int, tan: str) -> ImportResultDTO | TANRequiredDTO:
        session = self._sessions.get_by_id(session_id)

        if session.status != ImportStatus.TAN_REQUIRED:
            raise InvalidSessionState(f"Session {session_id} is not waiting for TAN")
        if not tan and not session.decoupled:
            raise InvalidSessionState(f"Session {session_id} requires a TAN")

        timeout = timedelta(minutes=self._timeout_minutes)
        if timezone.now() - session.started_at > timeout:
            self._sessions.delete(session.id)
            raise TanSessionExpiredError(f"Session {session_id} has expired")

        connection = self._connections.get_by_id(session.connection_id)
        mapping = self._mappings.get_by_id(session.mapping_id)

        result = self._fints.submit_tan(
            connection,
            session.client_state_blob,
            session.dialog_state_blob,
            session.tan_state_blob,
            tan,
            mapping.bank_account_iban,
            session.start_date,
            session.end_date,
            session.resume_transaction_fetch,
            session.decoupled,
        )

        if isinstance(result, TANChallenge):
            session.challenge_text = result.challenge_text
            session.client_state_blob = result.client_state_blob
            session.dialog_state_blob = result.dialog_state_blob
            session.tan_state_blob = result.tan_state_blob
            session.decoupled = result.decoupled
            session.resume_transaction_fetch = result.resume_transaction_fetch
            self._sessions.save(session)
            return TANRequiredDTO(session_id=session.id, challenge_text=result.challenge_text, decoupled=result.decoupled)

        self._sessions.delete(session.id)
        return export_to_actual(result, mapping, self._actual)
