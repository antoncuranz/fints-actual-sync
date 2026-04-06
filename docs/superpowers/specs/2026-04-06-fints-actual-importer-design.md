# FinTS-Actual Importer — Design Spec

## Overview

Django microservice that imports bank transactions from German banks via FinTS/HBCI (using python-fints) and exports them to Actual Budget (via actual-http-api REST API). Supports PIN/TAN challenge flow with pause/resume, encrypted budget support, and multiple Actual budgets on a single server.

Single-user tool, standalone Docker container, PostgreSQL, Django templates + HTMX for admin UI.

## Architecture

**Approach**: Synchronous import with state machine. Import runs synchronously within the API call. When a TAN challenge is hit, the FinTS client/dialog/TAN state is serialized to DB. A separate endpoint resumes the flow when the user submits a TAN.

No Celery, no background threads, no queue.

**Clean architecture layers** with dependency rule: `presentation` -> `application` -> `domain` <- `infrastructure`. Domain has zero framework dependencies.

### Project Structure

```
fints-actual-new/
├── config/                    # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── domain/                    # Pure Python, no Django dependency
│   ├── entities.py            # Dataclasses: BankConnection, ImportSession, AccountMapping, NormalizedTransaction, etc.
│   ├── ports.py               # Protocol interfaces: FinTSClientPort, ActualClientPort, CredentialStore
│   └── exceptions.py          # Domain-specific exceptions
├── application/               # Use cases, depends on domain only
│   ├── use_cases/
│   │   ├── import_transactions.py
│   │   ├── submit_tan.py
│   │   ├── manage_connections.py
│   │   └── manage_mappings.py
│   └── dto.py                 # Data transfer objects between layers
├── infrastructure/            # External integrations
│   ├── fints/
│   │   ├── client.py          # FinTSClientPort implementation (wraps python-fints)
│   │   └── state.py           # Serialize/deserialize client+TAN+dialog state helpers
│   ├── actual/
│   │   └── client.py          # ActualClientPort implementation (wraps actual-http-api REST)
│   ├── crypto/
│   │   └── fernet_store.py    # CredentialStore implementation via django-fernet-fields
│   └── persistence/
│       ├── models.py          # Django ORM models
│       └── repositories.py    # Domain repository implementations
├── presentation/              # Django views + templates
│   ├── views/
│   │   ├── connections.py     # CRUD for bank connections
│   │   ├── mappings.py        # Account mapping management
│   │   ├── import_api.py      # REST endpoints for import trigger + TAN submission
│   │   └── dashboard.py       # Overview / status page
│   ├── forms.py
│   └── templates/
│       └── ...                # Django templates + HTMX partials
├── manage.py
├── pyproject.toml
└── Dockerfile
```

## Domain Entities

All IDs are auto-increment integers for easy manual DB work. `product_id` and `product_version` are service-level config (env vars), not per-connection.

```python
@dataclass
class BankConnection:
    id: int
    name: str
    blz: str                         # Bankleitzahl
    url: str                         # FinTS endpoint URL
    user_id: str
    customer_id: str | None
    pin: str                         # Encrypted at rest via Fernet, decrypted in memory only

@dataclass
class BankAccount:
    iban: str
    account_number: str
    bank_identifier: str
    currency: str
    owner_name: str
    account_type: str

@dataclass
class AccountMapping:
    id: int
    connection_id: int
    bank_account_iban: str
    actual_budget_id: str            # Budget sync ID in Actual
    actual_account_id: str           # Account UUID within that budget
    budget_encryption_password: str | None  # For encrypted budgets, encrypted at rest

class ImportStatus(Enum):
    TAN_REQUIRED = "tan_required"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ImportSession:
    """Only persisted when a TAN challenge pauses the flow."""
    id: int
    connection_id: int
    mapping_id: int
    status: ImportStatus
    started_at: datetime
    challenge_text: str | None
    client_state_blob: bytes | None
    dialog_state_blob: bytes | None
    tan_state_blob: bytes | None
    error_message: str | None
    imported_count: int
    skipped_count: int

@dataclass
class NormalizedTransaction:
    """Mirrors Actual Budget transaction fields."""
    account: str                     # Actual account UUID (set during export)
    date: str                        # ISO date "YYYY-MM-DD"
    amount: int                      # Cents, negative=expense, positive=income
    payee_name: str                  # Actual resolves/matches payees on create
    imported_payee: str              # Raw payee string from bank
    imported_id: str                 # Idempotency key (FinTS bank reference)
    category: str | None
    notes: str | None
    cleared: bool
```

## Domain Ports

```python
class FinTSClientPort(Protocol):
    def fetch_accounts(self, connection: BankConnection) -> list[BankAccount]: ...
    def fetch_transactions(self, connection: BankConnection, iban: str, start_date: date, end_date: date | None) -> list[NormalizedTransaction] | TANChallenge: ...
    def submit_tan(self, connection: BankConnection, client_state: bytes, dialog_state: bytes, tan_state: bytes, tan: str) -> list[NormalizedTransaction] | TANChallenge: ...

class TANChallenge:
    challenge_text: str
    client_state_blob: bytes
    dialog_state_blob: bytes
    tan_state_blob: bytes

class ActualClientPort(Protocol):
    def import_transactions(self, budget_id: str, account_id: str, transactions: list[NormalizedTransaction], budget_encryption_password: str | None) -> ImportResult: ...
    def get_accounts(self, budget_id: str, budget_encryption_password: str | None) -> list[ActualAccount]: ...
    def get_budgets(self) -> list[ActualBudget]: ...

class ImportResult:
    added: list[str]
    updated: list[str]

class ActualAccount:
    id: str
    name: str

class ActualBudget:
    sync_id: str
    name: str

class CredentialStore(Protocol):
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...
```

- `FinTSClientPort` encapsulates all three python-fints serialization blobs inside `TANChallenge`. Application layer never handles raw blobs.
- `fetch_transactions` and `submit_tan` return either the transaction list or a `TANChallenge` (union type, no exceptions for flow control). Handles multi-TAN flows.
- `ActualClientPort.import_transactions` uses the `/transactions/import` endpoint which is idempotent by `imported_id` — Actual handles dedup natively.

## Application Use Cases

### Import Transactions

```python
class ImportTransactionsUseCase:
    def execute(self, mapping_id: int, start_date: date, end_date: date | None = None) -> ImportResultDTO | TANRequiredDTO:
        mapping = mapping_repo.get_by_id(mapping_id)
        connection = connection_repo.get_by_id(mapping.connection_id)
        connection.pin = credential_store.decrypt(connection.pin)

        result = fints_port.fetch_transactions(connection, mapping.bank_account_iban, start_date, end_date)

        if isinstance(result, TANChallenge):
            session = ImportSession(
                connection_id=connection.id, mapping_id=mapping.id,
                status=TAN_REQUIRED, started_at=now(),
                challenge_text=result.challenge_text,
                client_state_blob=result.client_state_blob,
                dialog_state_blob=result.dialog_state_blob,
                tan_state_blob=result.tan_state_blob,
            )
            session_repo.save(session)
            return TANRequiredDTO(session_id=session.id, challenge_text=result.challenge_text)

        return self._export_to_actual(result, mapping)

    def _export_to_actual(self, transactions, mapping) -> ImportResultDTO:
        for tx in transactions:
            tx.account = mapping.actual_account_id
        budget_pw = credential_store.decrypt(mapping.budget_encryption_password) if mapping.budget_encryption_password else None
        result = actual_port.import_transactions(mapping.actual_budget_id, mapping.actual_account_id, transactions, budget_pw)
        return ImportResultDTO(status="completed", imported=len(result.added), updated=len(result.updated))
```

- No session persisted on happy path — only when TAN is required.
- `_export_to_actual` shared between import and submit-tan use cases.

### Submit TAN

```python
class SubmitTANUseCase:
    def execute(self, session_id: int, tan: str) -> ImportResultDTO | TANRequiredDTO:
        session = session_repo.get_by_id(session_id)
        if session.status != TAN_REQUIRED:
            raise InvalidSessionState()

        connection = connection_repo.get_by_id(session.connection_id)
        mapping = mapping_repo.get_by_id(session.mapping_id)
        connection.pin = credential_store.decrypt(connection.pin)

        result = fints_port.submit_tan(
            connection, session.client_state_blob, session.dialog_state_blob, session.tan_state_blob, tan
        )

        if isinstance(result, TANChallenge):
            session.challenge_text = result.challenge_text
            session.client_state_blob = result.client_state_blob
            session.dialog_state_blob = result.dialog_state_blob
            session.tan_state_blob = result.tan_state_blob
            session_repo.save(session)
            return TANRequiredDTO(session_id=session.id, challenge_text=result.challenge_text)

        session_repo.delete(session)
        return self._export_to_actual(result, mapping)
```

- On completion, the temporary session is deleted.
- Multi-TAN supported: if bank requires another TAN, session is updated and TAN prompt re-rendered.

### Manage Connections

```python
class ManageConnectionsUseCase:
    def create(self, name, blz, url, user_id, customer_id, pin) -> BankConnectionDTO: ...
    def update(self, id, **kwargs) -> BankConnectionDTO: ...
    def delete(self, id) -> None: ...
    def discover_accounts(self, connection_id: int) -> list[BankAccountDTO] | TANRequiredDTO:
        """Open FinTS dialog, fetch SEPA accounts. May return TAN challenge."""
```

### Manage Mappings

```python
class ManageMappingsUseCase:
    def create(self, connection_id, bank_account_iban, actual_budget_id, actual_account_id, budget_encryption_password) -> AccountMappingDTO: ...
    def update(self, id, **kwargs) -> AccountMappingDTO: ...
    def delete(self, id) -> None: ...
    def list_budgets(self) -> list[ActualBudgetDTO]: ...
    def list_accounts_for_budget(self, budget_id: str, budget_encryption_password: str | None) -> list[ActualAccountDTO]: ...
```

## Infrastructure: FinTS Adapter

```python
class FinTSClientAdapter:
    def __init__(self, product_id: str, product_version: str): ...

    def fetch_transactions(self, connection, iban, start_date, end_date) -> list[NormalizedTransaction] | TANChallenge:
        client = FinTS3PinTanClient(
            bank_identifier=connection.blz, user_id=connection.user_id,
            customer_id=connection.customer_id,
            product_id=self.product_id, product_version=self.product_version,
            pin=connection.pin,
        )
        with client:
            accounts = client.get_sepa_accounts()
            account = next(a for a in accounts if a.iban == iban)
            result = client.get_transactions(account, start_date, end_date)

        if isinstance(result, NeedTANResponse):
            return TANChallenge(
                challenge_text=result.challenge,
                client_state_blob=client.deconstruct(including_private=True),
                dialog_state_blob=client.pause_dialog(),
                tan_state_blob=result.get_data(),
            )

        return [self._normalize(tx) for tx in result]

    def submit_tan(self, connection, client_state, dialog_state, tan_state, tan) -> list[NormalizedTransaction] | TANChallenge:
        client = FinTS3PinTanClient(
            bank_identifier=connection.blz, user_id=connection.user_id,
            customer_id=connection.customer_id,
            product_id=self.product_id, product_version=self.product_version,
            pin=connection.pin, from_data=client_state,
        )
        tan_response = NeedRetryResponse.from_data(tan_state)
        with client.resume_dialog(dialog_state):
            result = client.send_tan(tan_response, tan)

        if isinstance(result, NeedTANResponse):
            return TANChallenge(
                challenge_text=result.challenge,
                client_state_blob=client.deconstruct(including_private=True),
                dialog_state_blob=client.pause_dialog(),
                tan_state_blob=result.get_data(),
            )

        return [self._normalize(tx) for tx in result]
```

- `product_id` and `product_version` from env vars (`FINTS_PRODUCT_ID`, `FINTS_PRODUCT_VERSION`).
- Fresh `FinTS3PinTanClient` per call, no long-lived state.
- Three serialization mechanisms from python-fints: `client.deconstruct()` for client state, `client.pause_dialog()` for dialog state, `NeedTANResponse.get_data()` for TAN state. All opaque `bytes` blobs stored in DB `BinaryField`s.
- Adapter owns all `fints.*` imports. Application layer never touches python-fints.

## Infrastructure: Actual Client Adapter

```python
class ActualClientAdapter:
    def __init__(self, base_url: str, api_key: str): ...

    def import_transactions(self, budget_id, account_id, transactions, budget_encryption_password) -> ImportResult:
        params = {}
        if budget_encryption_password:
            params["budgetEncryptionPassword"] = budget_encryption_password
        resp = self.session.post(
            f"{self.base_url}/budgets/{budget_id}/accounts/{account_id}/transactions/import",
            json={"transactions": [self._serialize(tx) for tx in transactions]},
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return ImportResult(added=data["added"], updated=data["updated"])

    def get_accounts(self, budget_id, budget_encryption_password) -> list[ActualAccount]: ...
    def get_budgets(self) -> list[ActualBudget]: ...
```

- Uses `httpx` sync client.
- `budgetEncryptionPassword` as query param for encrypted budgets.
- `/transactions/import` endpoint is idempotent by `imported_id` — returns `added` + `updated` lists.

## Presentation: REST API + UI

### REST Endpoints

```
POST   /api/connections/                                  # Create bank connection
GET    /api/connections/                                  # List connections
PATCH  /api/connections/{id}/                             # Update connection
DELETE /api/connections/{id}/                             # Delete connection
POST   /api/connections/{id}/discover-accounts/           # Discover bank accounts (may return TAN challenge)

POST   /api/mappings/                                     # Create mapping
GET    /api/mappings/                                     # List mappings
PATCH  /api/mappings/{id}/                                # Update mapping
DELETE /api/mappings/{id}/                                # Delete mapping
GET    /api/actual/budgets/                               # List Actual budgets
GET    /api/actual/budgets/{id}/accounts/                 # List accounts in budget

POST   /api/imports/                                      # Start import { mapping_id, start_date, end_date? }
POST   /api/imports/{session_id}/submit-tan/              # Submit TAN { tan }
```

### Response Shapes

Completed import:
```json
{ "status": "completed", "imported": 12, "updated": 3 }
```

TAN required:
```json
{ "status": "tan_required", "session_id": 42, "challenge_text": "Bitte geben Sie die TAN ein" }
```

### UI Pages (Django templates + HTMX)

- **Dashboard** `/` — connections + mappings overview
- **Connections** `/connections/` — CRUD, "Discover accounts" button
- **Mappings** `/mappings/` — CRUD with Actual budget/account dropdowns
- **TAN prompt** — HTMX partial, appears inline on TAN challenge. Shows challenge text + TAN input. Posts to submit-tan, HTMX swaps result.

TAN flow in UI:
1. User clicks "Import" on a mapping -> HTMX POST to `/api/imports/`
2. If `tan_required`, response renders TAN input partial inline
3. User enters TAN, submits -> HTMX POST to `/api/imports/{session_id}/submit-tan/`
4. Repeat if multi-TAN, or show success summary

## UI Design

Minimal, modern look. Django templates + HTMX. No frontend build step.

### Design System

- **Color palette**: White cards on light gray (`#f8f9fa`) background. Primary action: `#4361ee` blue. Danger: `#e63946` red
- **Typography**: System font stack (`-apple-system, Inter, sans-serif`). Dark navy text (`#1a1a2e`)
- **Spacing**: 16-20px padding inside cards, 16px gap between cards. Rounded corners (10px cards, 6px buttons)
- **Cards**: Subtle `box-shadow: 0 1px 3px rgba(0,0,0,0.08)`, no heavy borders
- **Encryption badge**: Lock icon with small text when budget is encrypted

### Dashboard (`/`)

Single-page card-based layout. Each bank connection is a card containing:
- **Card header**: Connection name, BLZ + user ID, edit/delete buttons
- **Card body**: Table of account mappings for this connection — bank account (IBAN masked, account type), → Actual account name, budget name (with lock icon if encrypted), Import button
- **Empty state**: "No account mappings yet. Add mapping" link

Top-right: "+ Add Connection" button.

### TAN Challenge Modal

When an import hits a TAN challenge, a centered overlay modal appears over the dimmed dashboard:
- **Lock icon** (🔐) in a yellow circle at top
- **Title**: "TAN Required" with connection → account subtitle
- **Challenge box**: Gray background card showing the bank's challenge text
- **TAN input**: Large font, centered, letter-spaced input field, auto-focused
- **Actions**: Cancel (outline) + Submit (blue) buttons side by side
- **Expiry countdown**: "Session expires in MM:SS" below buttons

On submit: HTMX swaps the modal content. If another TAN required, updates challenge. If completed, shows success summary and closes modal.

### Add Connection Form

Modal or inline form with fields: Name, BLZ, FinTS URL, User ID, Customer ID (optional), PIN. "Discover Accounts" button after saving fetches available bank accounts via FinTS (may also trigger TAN flow).

### Add Mapping Form

Dropdowns populated via HTMX: select bank account IBAN (from discovered accounts), select Actual budget (fetched from actual-http-api), select Actual account within that budget. Optional budget encryption password field.

## Error Handling

- **FinTS errors** wrapped in domain exceptions (`FinTSConnectionError`, `FinTSAuthenticationError`)
- **Actual API errors** — `httpx.HTTPStatusError` caught, surfaced as `ActualExportError`
- **Expired TAN sessions** — `TAN_SESSION_TIMEOUT_MINUTES` env var (default 15). Sessions older than this are rejected with `TanSessionExpiredError`
- **Partial failures** — if fetch succeeds but Actual export fails, transactions are lost. User re-triggers import; Actual's `imported_id` dedup prevents duplicates

## Configuration

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| `FINTS_PRODUCT_ID` | Yes | — | Registered product ID for python-fints |
| `FINTS_PRODUCT_VERSION` | Yes | — | Product version string |
| `ACTUAL_API_URL` | Yes | — | actual-http-api base URL |
| `ACTUAL_API_KEY` | Yes | — | API key for actual-http-api |
| `FERNET_KEY` | Yes | — | Symmetric key for credential encryption |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `SECRET_KEY` | Yes | — | Django secret key |
| `TAN_SESSION_TIMEOUT_MINUTES` | No | 15 | TAN session expiry |
| `DEBUG` | No | false | Django debug mode |
| `ALLOWED_HOSTS` | No | — | Django allowed hosts |

## Dependencies

- `django` — web framework
- `django-fernet-fields` — encrypted model fields
- `psycopg2` (or `psycopg` v3) — PostgreSQL driver
- `python-fints` — FinTS/HBCI client
- `httpx` — HTTP client for actual-http-api
- `htmx` — frontend interactivity (via CDN, no build step)
