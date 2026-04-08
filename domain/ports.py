from datetime import date
from typing import Protocol

from .entities import (
    AccountMapping,
    BankAccount,
    BankConnection,
    ImportSession,
    NormalizedTransaction,
)


class TANChallenge:
    def __init__(self, challenge_text: str, client_state_blob: bytes, dialog_state_blob: bytes, tan_state_blob: bytes):
        self.challenge_text = challenge_text
        self.client_state_blob = client_state_blob
        self.dialog_state_blob = dialog_state_blob
        self.tan_state_blob = tan_state_blob


class ImportResult:
    def __init__(self, added: list[str], updated: list[str]):
        self.added = added
        self.updated = updated


class ActualAccount:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name


class ActualBudget:
    def __init__(self, sync_id: str, name: str):
        self.sync_id = sync_id
        self.name = name


class FinTSClientPort(Protocol):
    def fetch_accounts(self, connection: BankConnection) -> list[BankAccount]: ...
    def fetch_transactions(self, connection: BankConnection, iban: str, start_date: date, end_date: date | None) -> list[NormalizedTransaction] | TANChallenge: ...
    def submit_tan(self, connection: BankConnection, client_state: bytes, dialog_state: bytes, tan_state: bytes, tan: str) -> list[NormalizedTransaction] | TANChallenge: ...


class ActualClientPort(Protocol):
    def import_transactions(self, budget_id: str, account_id: str, transactions: list[NormalizedTransaction], budget_encryption_password: str | None) -> ImportResult: ...
    def get_accounts(self, budget_id: str, budget_encryption_password: str | None) -> list[ActualAccount]: ...
    def get_budgets(self) -> list[ActualBudget]: ...


class CredentialStore(Protocol):
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...


class ConnectionRepository(Protocol):
    def get_by_id(self, id: int) -> BankConnection: ...
    def get_all(self) -> list[BankConnection]: ...
    def save(self, connection: BankConnection) -> BankConnection: ...
    def delete(self, id: int) -> None: ...


class MappingRepository(Protocol):
    def get_by_id(self, id: int) -> AccountMapping: ...
    def get_all(self) -> list[AccountMapping]: ...
    def get_by_connection_id(self, connection_id: int) -> list[AccountMapping]: ...
    def save(self, mapping: AccountMapping) -> AccountMapping: ...
    def delete(self, id: int) -> None: ...


class SessionRepository(Protocol):
    def get_by_id(self, id: int) -> ImportSession: ...
    def save(self, session: ImportSession) -> ImportSession: ...
    def delete(self, id: int) -> None: ...


class NotificationPort(Protocol):
    def notify_tan_required(self, session_id: int, challenge_text: str, tan_submit_url: str) -> None: ...
