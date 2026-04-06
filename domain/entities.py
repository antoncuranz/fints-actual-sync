from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


@dataclass
class BankConnection:
    id: int = 0
    name: str = ""
    blz: str = ""
    url: str = ""
    user_id: str = ""
    customer_id: str | None = None
    pin: str = ""


@dataclass
class BankAccount:
    iban: str = ""
    account_number: str = ""
    bank_identifier: str = ""
    currency: str = ""
    owner_name: str = ""
    account_type: str = ""


@dataclass
class AccountMapping:
    id: int = 0
    connection_id: int = 0
    bank_account_iban: str = ""
    actual_budget_id: str = ""
    actual_account_id: str = ""
    budget_encryption_password: str | None = None


class ImportStatus(Enum):
    TAN_REQUIRED = "tan_required"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ImportSession:
    id: int = 0
    connection_id: int = 0
    mapping_id: int = 0
    status: ImportStatus = ImportStatus.TAN_REQUIRED
    started_at: datetime = field(default_factory=datetime.now)
    challenge_text: str | None = None
    client_state_blob: bytes | None = None
    dialog_state_blob: bytes | None = None
    tan_state_blob: bytes | None = None
    error_message: str | None = None
    imported_count: int = 0
    skipped_count: int = 0


@dataclass
class NormalizedTransaction:
    account: str = ""
    date: str = ""
    amount: int = 0
    payee_name: str = ""
    imported_payee: str = ""
    imported_id: str = ""
    category: str | None = None
    notes: str | None = None
    cleared: bool = False
