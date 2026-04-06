from datetime import datetime

from application.dto import ImportResultDTO, TANRequiredDTO
from domain.entities import ImportSession, ImportStatus
from domain.ports import (
    ActualClientPort,
    ConnectionRepository,
    CredentialStore,
    FinTSClientPort,
    MappingRepository,
    SessionRepository,
    TANChallenge,
)


class ImportTransactionsUseCase:
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

    def execute(self, mapping_id: int, start_date, end_date=None) -> ImportResultDTO | TANRequiredDTO:
        mapping = self._mappings.get_by_id(mapping_id)
        connection = self._connections.get_by_id(mapping.connection_id)

        result = self._fints.fetch_transactions(connection, mapping.bank_account_iban, start_date, end_date)

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
            ))
            return TANRequiredDTO(session_id=session.id, challenge_text=result.challenge_text)

        return self._export_to_actual(result, mapping)

    def _export_to_actual(self, transactions, mapping) -> ImportResultDTO:
        for tx in transactions:
            tx.account = mapping.actual_account_id
        budget_pw = mapping.budget_encryption_password
        result = self._actual.import_transactions(mapping.actual_budget_id, mapping.actual_account_id, transactions, budget_pw)
        return ImportResultDTO(status="completed", imported=len(result.added), updated=len(result.updated))
