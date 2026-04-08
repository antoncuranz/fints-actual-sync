from dataclasses import dataclass


@dataclass
class ImportResultDTO:
    status: str
    imported: int = 0
    updated: int = 0


@dataclass
class TANRequiredDTO:
    session_id: int
    challenge_text: str
    status: str = "tan_required"


@dataclass
class BankConnectionDTO:
    id: int
    name: str
    blz: str
    url: str
    user_id: str
    customer_id: str | None


@dataclass
class AccountMappingDTO:
    id: int
    connection_id: int
    bank_account_iban: str
    actual_budget_id: str
    actual_account_id: str
    has_encryption_password: bool


@dataclass
class BankAccountDTO:
    iban: str
    account_number: str
    currency: str
    owner_name: str
    account_type: str


@dataclass
class ActualBudgetDTO:
    sync_id: str
    name: str


@dataclass
class ActualAccountDTO:
    id: str
    name: str


@dataclass
class SyncAllItemResult:
    mapping_id: int
    status: str
    imported: int = 0
    session_id: int | None = None
    error: str | None = None


@dataclass
class SyncAllResultDTO:
    results: list[SyncAllItemResult]
