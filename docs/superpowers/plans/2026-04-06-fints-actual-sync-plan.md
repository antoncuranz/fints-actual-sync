# FinTS-Actual Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Django microservice that imports bank transactions via FinTS and exports them to Actual Budget, with PIN/TAN challenge support.

**Architecture:** Synchronous import with serialized state machine. Clean architecture layers: domain (pure Python) → application (use cases) → infrastructure (adapters) → presentation (Django + HTMX). TAN challenges pause the flow by serializing python-fints state blobs to DB.

**Tech Stack:** Django, PostgreSQL, python-fints, actual-http-api (REST), httpx, django-fernet-fields, HTMX

**Repo:** https://github.com/antoncuranz/fints-actual-sync

**Design spec:** `docs/superpowers/specs/2026-04-06-fints-actual-importer-design.md`

---

## Phase 1: Foundation (Task 1)

No dependencies. Creates project skeleton, domain layer, and all config.

## Phase 2: Infrastructure + Application (Tasks 2-4, parallel)

All depend on Phase 1. Can run simultaneously:
- Task 2: Persistence (Django models, repos, migrations)
- Task 3: Infrastructure adapters (FinTS, Actual, Crypto)
- Task 4: Application use cases

## Phase 3: Presentation (Task 5)

Depends on Phase 2. Django views, templates, HTMX UI.

---

## Task 1: Django Project Scaffold + Domain Layer

**Files:**
- Create: `manage.py`
- Create: `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`
- Create: `domain/__init__.py`, `domain/entities.py`, `domain/ports.py`, `domain/exceptions.py`
- Create: `application/__init__.py`, `application/dto.py`
- Create: `infrastructure/__init__.py`
- Create: `infrastructure/fints/__init__.py`
- Create: `infrastructure/actual/__init__.py`
- Create: `infrastructure/crypto/__init__.py`
- Create: `infrastructure/persistence/__init__.py`
- Create: `presentation/__init__.py`
- Create: `presentation/views/__init__.py`
- Create: `presentation/templates/base.html`
- Create: `pyproject.toml`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "fints-actual-sync"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "django>=5.1",
    "django-fernet-fields",
    "psycopg[binary]",
    "python-fints",
    "httpx",
    "dj-database-url",
    "python-dotenv",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-django",
    "factory-boy",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 2: Create Django config package**

`config/__init__.py` — empty.

`config/settings.py`:
```python
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "fernet_fields",
    "infrastructure.persistence",
    "presentation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", "sqlite:///db.sqlite3"),
        conn_max_age=600,
    )
}

FERNET_KEY = os.getenv("FERNET_KEY", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"

FINTS_PRODUCT_ID = os.getenv("FINTS_PRODUCT_ID", "")
FINTS_PRODUCT_VERSION = os.getenv("FINTS_PRODUCT_VERSION", "")

ACTUAL_API_URL = os.getenv("ACTUAL_API_URL", "http://localhost:5007/v1")
ACTUAL_API_KEY = os.getenv("ACTUAL_API_KEY", "")

TAN_SESSION_TIMEOUT_MINUTES = int(os.getenv("TAN_SESSION_TIMEOUT_MINUTES", "15"))
```

`config/urls.py`:
```python
from django.urls import include, path

urlpatterns = [
    path("", include("presentation.views")),
]
```

`config/wsgi.py`:
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
```

- [ ] **Step 3: Create manage.py**

```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
```

- [ ] **Step 4: Create domain layer**

`domain/__init__.py` — empty.

`domain/entities.py`:
```python
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
```

`domain/ports.py`:
```python
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
```

`domain/exceptions.py`:
```python
class FinTSConnectionError(Exception):
    pass


class FinTSAuthenticationError(Exception):
    pass


class ActualExportError(Exception):
    pass


class InvalidSessionState(Exception):
    pass


class TanSessionExpiredError(Exception):
    pass
```

- [ ] **Step 5: Create application layer stubs**

`application/__init__.py` — empty.

`application/dto.py`:
```python
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
```

- [ ] **Step 6: Create infrastructure package stubs**

Create all `__init__.py` files as empty files for:
- `infrastructure/`, `infrastructure/fints/`, `infrastructure/actual/`, `infrastructure/crypto/`, `infrastructure/persistence/`

- [ ] **Step 7: Create presentation package stubs**

Create `presentation/__init__.py` and `presentation/views/__init__.py` as empty.

`presentation/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}FinTS → Actual{% endblock %}</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif; background: #f8f9fa; color: #1a1a2e; }
        .container { max-width: 960px; margin: 0 auto; padding: 24px; }
        .card { background: white; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px; overflow: hidden; }
        .card-header { padding: 16px 20px; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center; }
        .card-body { padding: 16px 20px; }
        .btn { padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; border: none; text-decoration: none; }
        .btn-primary { background: #4361ee; color: white; }
        .btn-outline { background: none; border: 1px solid #ddd; color: #666; }
        .btn-danger { background: none; border: 1px solid #ddd; color: #e63946; }
        .btn-sm { padding: 4px 10px; font-size: 11px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { padding: 8px 20px; text-align: left; font-weight: 500; color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; background: #fafafa; }
        td { padding: 12px 20px; }
        tr { border-top: 1px solid #f5f5f5; }
        .text-muted { color: #888; }
        .text-small { font-size: 12px; }
        .text-smaller { font-size: 11px; }
        .fw-600 { font-weight: 600; }
        .mt-4 { margin-top: 16px; }
        .mb-2 { margin-bottom: 8px; }
        .flex { display: flex; }
        .gap-2 { gap: 8px; }
        .justify-between { justify-content: space-between; }
        .items-center { align-items: center; }
        .overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 100; }
        .modal { background: white; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.12); padding: 28px; width: 380px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 12px; color: #666; margin-bottom: 6px; }
        .form-group input, .form-group select { width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        .text-center { text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 8: Create .gitignore, Dockerfile, docker-compose.yml, .env**

`.gitignore`:
```
.superpowers/
.env
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.eggs/
db.sqlite3
.pytest_cache/
```

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

`docker-compose.yml`:
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: fints_actual
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

`.env` (local dev defaults):
```
FINTS_PRODUCT_ID=
FINTS_PRODUCT_VERSION=
ACTUAL_API_URL=http://localhost:5007/v1
ACTUAL_API_KEY=
FERNET_KEY=
DATABASE_URL=postgres://postgres:postgres@db:5432/fints_actual
SECRET_KEY=dev-secret-key-change-in-prod
TAN_SESSION_TIMEOUT_MINUTES=15
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
```

- [ ] **Step 9: Verify project setup**

Run: `pip install -e ".[dev]" && python manage.py check`
Expected: Django system check passes with no errors.

- [ ] **Step 10: Commit and push**

```bash
git add -A && git commit -m "feat: project scaffold, domain layer, Django config" && git push
```

---

## Task 2: Persistence Layer

**Depends on:** Task 1

**Files:**
- Create: `infrastructure/persistence/models.py`
- Create: `infrastructure/persistence/repositories.py`

- [ ] **Step 1: Create Django models**

`infrastructure/persistence/models.py`:
```python
from django.db import models
from fernet_fields import EncryptedCharField


class BankConnectionModel(models.Model):
    name = models.CharField(max_length=255)
    blz = models.CharField(max_length=8)
    url = models.URLField()
    user_id = models.CharField(max_length=255)
    customer_id = models.CharField(max_length=255, blank=True, default="")
    pin = EncryptedCharField(max_length=255)

    class Meta:
        app_label = "persistence"
        db_table = "bank_connections"

    def __str__(self):
        return self.name


class AccountMappingModel(models.Model):
    connection = models.ForeignKey(BankConnectionModel, on_delete=models.CASCADE, related_name="mappings")
    bank_account_iban = models.CharField(max_length=34)
    actual_budget_id = models.CharField(max_length=255)
    actual_account_id = models.CharField(max_length=255)
    budget_encryption_password = EncryptedCharField(max_length=255, blank=True, default="")

    class Meta:
        app_label = "persistence"
        db_table = "account_mappings"

    def __str__(self):
        return f"{self.bank_account_iban} → {self.actual_account_id}"


class ImportSessionModel(models.Model):
    STATUS_CHOICES = [
        ("tan_required", "TAN Required"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    connection = models.ForeignKey(BankConnectionModel, on_delete=models.CASCADE)
    mapping = models.ForeignKey(AccountMappingModel, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    started_at = models.DateTimeField(auto_now_add=True)
    challenge_text = models.TextField(blank=True, default="")
    client_state_blob = models.BinaryField(null=True, blank=True)
    dialog_state_blob = models.BinaryField(null=True, blank=True)
    tan_state_blob = models.BinaryField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    imported_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)

    class Meta:
        app_label = "persistence"
        db_table = "import_sessions"
```

- [ ] **Step 2: Create repositories**

`infrastructure/persistence/repositories.py`:
```python
from datetime import datetime

from domain.entities import AccountMapping, BankConnection, ImportSession, ImportStatus
from domain.exceptions import InvalidSessionState
from domain.ports import CredentialStore

from .models import AccountMappingModel, BankConnectionModel, ImportSessionModel


class ConnectionRepository:
    def __init__(self, credential_store: CredentialStore | None = None):
        self._credential_store = credential_store

    def get_by_id(self, id: int) -> BankConnection:
        obj = BankConnectionModel.objects.get(pk=id)
        return self._to_entity(obj)

    def get_all(self) -> list[BankConnection]:
        return [self._to_entity(obj) for obj in BankConnectionModel.objects.all()]

    def save(self, connection: BankConnection) -> BankConnection:
        pin = connection.pin
        if self._credential_store and connection.id == 0:
            pin = self._credential_store.encrypt(pin)
        defaults = {
            "name": connection.name,
            "blz": connection.blz,
            "url": connection.url,
            "user_id": connection.user_id,
            "customer_id": connection.customer_id or "",
            "pin": pin,
        }
        if connection.id:
            obj, _ = BankConnectionModel.objects.update_or_create(pk=connection.id, defaults=defaults)
        else:
            obj = BankConnectionModel.objects.create(**defaults)
        return self._to_entity(obj)

    def delete(self, id: int) -> None:
        BankConnectionModel.objects.filter(pk=id).delete()

    def _to_entity(self, obj: BankConnectionModel) -> BankConnection:
        pin = obj.pin
        if self._credential_store:
            pin = self._credential_store.decrypt(pin)
        return BankConnection(
            id=obj.id, name=obj.name, blz=obj.blz, url=obj.url,
            user_id=obj.user_id, customer_id=obj.customer_id or None, pin=pin,
        )


class MappingRepository:
    def get_by_id(self, id: int) -> AccountMapping:
        obj = AccountMappingModel.objects.get(pk=id)
        return self._to_entity(obj)

    def get_all(self) -> list[AccountMapping]:
        return [self._to_entity(obj) for obj in AccountMappingModel.objects.all()]

    def get_by_connection_id(self, connection_id: int) -> list[AccountMapping]:
        return [self._to_entity(obj) for obj in AccountMappingModel.objects.filter(connection_id=connection_id)]

    def save(self, mapping: AccountMapping) -> AccountMapping:
        defaults = {
            "connection_id": mapping.connection_id,
            "bank_account_iban": mapping.bank_account_iban,
            "actual_budget_id": mapping.actual_budget_id,
            "actual_account_id": mapping.actual_account_id,
            "budget_encryption_password": mapping.budget_encryption_password or "",
        }
        if mapping.id:
            obj, _ = AccountMappingModel.objects.update_or_create(pk=mapping.id, defaults=defaults)
        else:
            obj = AccountMappingModel.objects.create(**defaults)
        return self._to_entity(obj)

    def delete(self, id: int) -> None:
        AccountMappingModel.objects.filter(pk=id).delete()

    def _to_entity(self, obj: AccountMappingModel) -> AccountMapping:
        return AccountMapping(
            id=obj.id, connection_id=obj.connection_id,
            bank_account_iban=obj.bank_account_iban,
            actual_budget_id=obj.actual_budget_id,
            actual_account_id=obj.actual_account_id,
            budget_encryption_password=obj.budget_encryption_password or None,
        )


class SessionRepository:
    def get_by_id(self, id: int) -> ImportSession:
        obj = ImportSessionModel.objects.get(pk=id)
        return self._to_entity(obj)

    def save(self, session: ImportSession) -> ImportSession:
        defaults = {
            "connection_id": session.connection_id,
            "mapping_id": session.mapping_id,
            "status": session.status.value,
            "challenge_text": session.challenge_text or "",
            "client_state_blob": session.client_state_blob,
            "dialog_state_blob": session.dialog_state_blob,
            "tan_state_blob": session.tan_state_blob,
            "error_message": session.error_message or "",
            "imported_count": session.imported_count,
            "skipped_count": session.skipped_count,
        }
        if session.id:
            obj, _ = ImportSessionModel.objects.update_or_create(pk=session.id, defaults=defaults)
        else:
            obj = ImportSessionModel.objects.create(**defaults)
        return self._to_entity(obj)

    def delete(self, id: int) -> None:
        ImportSessionModel.objects.filter(pk=id).delete()

    def _to_entity(self, obj: ImportSessionModel) -> ImportSession:
        return ImportSession(
            id=obj.id, connection_id=obj.connection_id,
            mapping_id=obj.mapping_id,
            status=ImportStatus(obj.status),
            started_at=obj.started_at,
            challenge_text=obj.challenge_text or None,
            client_state_blob=bytes(obj.client_state_blob) if obj.client_state_blob else None,
            dialog_state_blob=bytes(obj.dialog_state_blob) if obj.dialog_state_blob else None,
            tan_state_blob=bytes(obj.tan_state_blob) if obj.tan_state_blob else None,
            error_message=obj.error_message or None,
            imported_count=obj.imported_count,
            skipped_count=obj.skipped_count,
        )
```

- [ ] **Step 3: Run makemigrations and migrate**

Run: `python manage.py makemigrations persistence && python manage.py migrate`
Expected: Migrations created and applied successfully.

- [ ] **Step 4: Commit and push**

```bash
git add -A && git commit -m "feat: persistence layer — models and repositories" && git push
```

---

## Task 3: Infrastructure Adapters (FinTS, Actual, Crypto)

**Depends on:** Task 1

**Files:**
- Create: `infrastructure/crypto/fernet_store.py`
- Create: `infrastructure/fints/client.py`
- Create: `infrastructure/actual/client.py`

- [ ] **Step 1: Create Fernet credential store**

`infrastructure/crypto/fernet_store.py`:
```python
from cryptography.fernet import Fernet
from django.conf import settings

from domain.ports import CredentialStore


class FernetCredentialStore:
    def __init__(self):
        self._fernet = Fernet(settings.FERNET_KEY.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 2: Create FinTS adapter**

`infrastructure/fints/client.py`:
```python
import datetime
import logging
from dataclasses import dataclass

from fints.client import FinTS3PinTanClient, NeedRetryResponse, NeedTANResponse
from fints.models import SEPAAccount

from domain.entities import BankAccount, BankConnection, NormalizedTransaction
from domain.ports import TANChallenge

logger = logging.getLogger(__name__)


class FinTSClientAdapter:
    def __init__(self, product_id: str, product_version: str):
        self.product_id = product_id
        self.product_version = product_version

    def _create_client(self, connection: BankConnection, from_data: bytes | None = None) -> FinTS3PinTanClient:
        return FinTS3PinTanClient(
            bank_identifier=connection.blz,
            user_id=connection.user_id,
            customer_id=connection.customer_id or connection.user_id,
            product_id=self.product_id,
            product_version=self.product_version,
            pin=connection.pin,
            from_data=from_data,
        )

    def fetch_accounts(self, connection: BankConnection) -> list[BankAccount]:
        client = self._create_client(connection)
        with client:
            sepa_accounts = client.get_sepa_accounts()
            info = client.get_information()
            accounts_info = {a["iban"]: a for a in info.get("accounts", [])}
            result = []
            for sa in sepa_accounts:
                detail = accounts_info.get(sa.iban, {})
                result.append(BankAccount(
                    iban=sa.iban,
                    account_number=sa.account_number,
                    bank_identifier=str(sa.bic) if sa.bic else "",
                    currency=sa.currency or detail.get("currency", "EUR"),
                    owner_name=", ".join(detail.get("owner_name", [""])),
                    account_type=str(detail.get("type", "")),
                ))
            return result

    def fetch_transactions(self, connection: BankConnection, iban: str, start_date: datetime.date, end_date: datetime.date | None) -> list[NormalizedTransaction] | TANChallenge:
        client = self._create_client(connection)
        with client:
            accounts = client.get_sepa_accounts()
            account = next(a for a in accounts if a.iban == iban)
            result = client.get_transactions(account, start_date, end_date)

        if isinstance(result, NeedTANResponse):
            return TANChallenge(
                challenge_text=result.challenge or "Please enter TAN",
                client_state_blob=client.deconstruct(including_private=True),
                dialog_state_blob=client.pause_dialog(),
                tan_state_blob=result.get_data(),
            )

        return [self._normalize(tx) for tx in result]

    def submit_tan(self, connection: BankConnection, client_state: bytes, dialog_state: bytes, tan_state: bytes, tan: str) -> list[NormalizedTransaction] | TANChallenge:
        client = self._create_client(connection, from_data=client_state)
        tan_response = NeedRetryResponse.from_data(tan_state)
        with client.resume_dialog(dialog_state):
            result = client.send_tan(tan_response, tan)

        if isinstance(result, NeedTANResponse):
            return TANChallenge(
                challenge_text=result.challenge or "Please enter TAN",
                client_state_blob=client.deconstruct(including_private=True),
                dialog_state_blob=client.pause_dialog(),
                tan_state_blob=result.get_data(),
            )

        return [self._normalize(tx) for tx in result]

    def _normalize(self, tx) -> NormalizedTransaction:
        data = tx.data if hasattr(tx, "data") else {}
        amount = tx.amount if hasattr(tx, "amount") else 0
        if hasattr(amount, "amount"):
            amount_val = int(amount.amount * 100)
        else:
            amount_val = int(float(str(amount).replace(",", ".")) * 100)

        date_str = ""
        if hasattr(tx, "date"):
            date_str = tx.date.isoformat() if hasattr(tx.date, "isoformat") else str(tx.date)
        elif "date" in data:
            d = data["date"]
            date_str = d.isoformat() if hasattr(d, "isoformat") else str(d)

        applicant_name = data.get("applicant_name", "")
        purpose = data.get("purpose", "")
        bank_ref = data.get("bank_reference", "") or data.get("transaction_id", "")

        return NormalizedTransaction(
            date=date_str,
            amount=amount_val,
            payee_name=applicant_name,
            imported_payee=applicant_name,
            imported_id=bank_ref,
            notes=purpose,
            cleared=False,
        )
```

- [ ] **Step 3: Create Actual client adapter**

`infrastructure/actual/client.py`:
```python
import httpx

from domain.entities import NormalizedTransaction
from domain.ports import ActualAccount, ActualBudget, ImportResult


class ActualClientAdapter:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(headers={"X-API-Key": api_key}, timeout=30.0)

    def import_transactions(self, budget_id: str, account_id: str, transactions: list[NormalizedTransaction], budget_encryption_password: str | None) -> ImportResult:
        params = {}
        if budget_encryption_password:
            params["budgetEncryptionPassword"] = budget_encryption_password

        payload = {"transactions": [self._serialize(tx) for tx in transactions]}
        resp = self._client.post(
            f"{self._base_url}/budgets/{budget_id}/accounts/{account_id}/transactions/import",
            json=payload,
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return ImportResult(added=data.get("added", []), updated=data.get("updated", []))

    def get_accounts(self, budget_id: str, budget_encryption_password: str | None) -> list[ActualAccount]:
        params = {}
        if budget_encryption_password:
            params["budgetEncryptionPassword"] = budget_encryption_password
        resp = self._client.get(f"{self._base_url}/budgets/{budget_id}/accounts", params=params)
        resp.raise_for_status()
        return [ActualAccount(id=a["id"], name=a["name"]) for a in resp.json().get("data", [])]

    def get_budgets(self) -> list[ActualBudget]:
        resp = self._client.get(f"{self._base_url}/budgets")
        resp.raise_for_status()
        return [ActualBudget(sync_id=b.get("sync_id", b.get("id", "")), name=b.get("name", "")) for b in resp.json().get("data", [])]

    def _serialize(self, tx: NormalizedTransaction) -> dict:
        result = {
            "account": tx.account,
            "date": tx.date,
            "amount": tx.amount,
            "payee_name": tx.payee_name,
            "imported_payee": tx.imported_payee,
            "imported_id": tx.imported_id,
            "cleared": tx.cleared,
        }
        if tx.notes:
            result["notes"] = tx.notes
        if tx.category:
            result["category"] = tx.category
        return result
```

- [ ] **Step 4: Commit and push**

```bash
git add -A && git commit -m "feat: FinTS, Actual, and Crypto infrastructure adapters" && git push
```

---

## Task 4: Application Use Cases

**Depends on:** Task 1

**Files:**
- Create: `application/use_cases/__init__.py`
- Create: `application/use_cases/import_transactions.py`
- Create: `application/use_cases/submit_tan.py`
- Create: `application/use_cases/manage_connections.py`
- Create: `application/use_cases/manage_mappings.py`

- [ ] **Step 1: Create import transactions use case**

`application/use_cases/__init__.py` — empty.

`application/use_cases/import_transactions.py`:
```python
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
        connection.pin = self._creds.decrypt(connection.pin)

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
        budget_pw = self._creds.decrypt(mapping.budget_encryption_password) if mapping.budget_encryption_password else None
        result = self._actual.import_transactions(mapping.actual_budget_id, mapping.actual_account_id, transactions, budget_pw)
        return ImportResultDTO(status="completed", imported=len(result.added), updated=len(result.updated))
```

- [ ] **Step 2: Create submit TAN use case**

`application/use_cases/submit_tan.py`:
```python
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
        connection.pin = self._creds.decrypt(connection.pin)

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
        budget_pw = self._creds.decrypt(mapping.budget_encryption_password) if mapping.budget_encryption_password else None
        result = self._actual.import_transactions(mapping.actual_budget_id, mapping.actual_account_id, transactions, budget_pw)
        return ImportResultDTO(status="completed", imported=len(result.added), updated=len(result.updated))
```

- [ ] **Step 3: Create manage connections use case**

`application/use_cases/manage_connections.py`:
```python
from datetime import datetime

from application.dto import BankAccountDTO, BankConnectionDTO, TANRequiredDTO
from domain.entities import BankConnection
from domain.ports import ConnectionRepository, CredentialStore, FinTSClientPort, SessionRepository, TANChallenge


class ManageConnectionsUseCase:
    def __init__(
        self,
        connection_repo: ConnectionRepository,
        credential_store: CredentialStore,
        fints_port: FinTSClientPort | None = None,
    ):
        self._connections = connection_repo
        self._creds = credential_store
        self._fints = fints_port

    def create(self, name: str, blz: str, url: str, user_id: str, customer_id: str | None, pin: str) -> BankConnectionDTO:
        connection = self._connections.save(BankConnection(
            name=name, blz=blz, url=url, user_id=user_id, customer_id=customer_id, pin=pin,
        ))
        return self._to_dto(connection)

    def update(self, id: int, **kwargs) -> BankConnectionDTO:
        connection = self._connections.get_by_id(id)
        for key, value in kwargs.items():
            if value is not None and hasattr(connection, key):
                setattr(connection, key, value)
        connection = self._connections.save(connection)
        return self._to_dto(connection)

    def delete(self, id: int) -> None:
        self._connections.delete(id)

    def list_all(self) -> list[BankConnectionDTO]:
        return [self._to_dto(c) for c in self._connections.get_all()]

    def discover_accounts(self, connection_id: int) -> list[BankAccountDTO] | TANRequiredDTO:
        if not self._fints:
            raise RuntimeError("FinTS client not configured")
        connection = self._connections.get_by_id(connection_id)
        connection.pin = self._creds.decrypt(connection.pin)
        result = self._fints.fetch_accounts(connection)
        if isinstance(result, TANChallenge):
            return TANRequiredDTO(session_id=0, challenge_text=result.challenge_text)
        return [BankAccountDTO(iban=a.iban, account_number=a.account_number, currency=a.currency, owner_name=a.owner_name, account_type=a.account_type) for a in result]

    def _to_dto(self, connection: BankConnection) -> BankConnectionDTO:
        return BankConnectionDTO(
            id=connection.id, name=connection.name, blz=connection.blz,
            url=connection.url, user_id=connection.user_id, customer_id=connection.customer_id,
        )
```

- [ ] **Step 4: Create manage mappings use case**

`application/use_cases/manage_mappings.py`:
```python
from application.dto import AccountMappingDTO, ActualAccountDTO, ActualBudgetDTO
from domain.entities import AccountMapping
from domain.ports import ActualClientPort, CredentialStore, MappingRepository


class ManageMappingsUseCase:
    def __init__(self, mapping_repo: MappingRepository, actual_port: ActualClientPort, credential_store: CredentialStore):
        self._mappings = mapping_repo
        self._actual = actual_port
        self._creds = credential_store

    def create(self, connection_id: int, bank_account_iban: str, actual_budget_id: str, actual_account_id: str, budget_encryption_password: str | None) -> AccountMappingDTO:
        mapping = self._mappings.save(AccountMapping(
            connection_id=connection_id, bank_account_iban=bank_account_iban,
            actual_budget_id=actual_budget_id, actual_account_id=actual_account_id,
            budget_encryption_password=budget_encryption_password,
        ))
        return self._to_dto(mapping)

    def update(self, id: int, **kwargs) -> AccountMappingDTO:
        mapping = self._mappings.get_by_id(id)
        for key, value in kwargs.items():
            if value is not None and hasattr(mapping, key):
                setattr(mapping, key, value)
        mapping = self._mappings.save(mapping)
        return self._to_dto(mapping)

    def delete(self, id: int) -> None:
        self._mappings.delete(id)

    def list_all(self) -> list[AccountMappingDTO]:
        return [self._to_dto(m) for m in self._mappings.get_all()]

    def list_for_connection(self, connection_id: int) -> list[AccountMappingDTO]:
        return [self._to_dto(m) for m in self._mappings.get_by_connection_id(connection_id)]

    def list_budgets(self) -> list[ActualBudgetDTO]:
        budgets = self._actual.get_budgets()
        return [ActualBudgetDTO(sync_id=b.sync_id, name=b.name) for b in budgets]

    def list_accounts_for_budget(self, budget_id: str, budget_encryption_password: str | None = None) -> list[ActualAccountDTO]:
        pw = self._creds.decrypt(budget_encryption_password) if budget_encryption_password else None
        accounts = self._actual.get_accounts(budget_id, pw)
        return [ActualAccountDTO(id=a.id, name=a.name) for a in accounts]

    def _to_dto(self, mapping: AccountMapping) -> AccountMappingDTO:
        return AccountMappingDTO(
            id=mapping.id, connection_id=mapping.connection_id,
            bank_account_iban=mapping.bank_account_iban,
            actual_budget_id=mapping.actual_budget_id,
            actual_account_id=mapping.actual_account_id,
            has_encryption_password=bool(mapping.budget_encryption_password),
        )
```

- [ ] **Step 5: Commit and push**

```bash
git add -A && git commit -m "feat: application use cases — import, TAN, connections, mappings" && git push
```

---

## Task 5: Presentation Layer (Views + Templates + HTMX UI)

**Depends on:** Tasks 2, 3, 4

**Files:**
- Create: `presentation/views/__init__.py` (replace empty with URL registrations)
- Create: `presentation/views/dashboard.py`
- Create: `presentation/views/connections.py`
- Create: `presentation/views/mappings.py`
- Create: `presentation/views/import_api.py`
- Create: `presentation/forms.py`
- Create: `presentation/templates/dashboard.html`
- Create: `presentation/templates/partials/connection_card.html`
- Create: `presentation/templates/partials/tan_modal.html`
- Create: `presentation/templates/partials/import_result.html`
- Create: `presentation/templates/partials/connection_form.html`
- Create: `presentation/templates/partials/mapping_form.html`
- Create: `presentation/dependency_config.py`

- [ ] **Step 1: Create dependency injection config**

`presentation/dependency_config.py`:
```python
from django.conf import settings

from application.use_cases.import_transactions import ImportTransactionsUseCase
from application.use_cases.manage_connections import ManageConnectionsUseCase
from application.use_cases.manage_mappings import ManageMappingsUseCase
from application.use_cases.submit_tan import SubmitTANUseCase
from infrastructure.actual.client import ActualClientAdapter
from infrastructure.crypto.fernet_store import FernetCredentialStore
from infrastructure.fints.client import FinTSClientAdapter
from infrastructure.persistence.repositories import (
    ConnectionRepository,
    MappingRepository,
    SessionRepository,
)


def get_credential_store() -> FernetCredentialStore:
    return FernetCredentialStore()


def get_fints_client() -> FinTSClientAdapter:
    return FinTSClientAdapter(settings.FINTS_PRODUCT_ID, settings.FINTS_PRODUCT_VERSION)


def get_actual_client() -> ActualClientAdapter:
    return ActualClientAdapter(settings.ACTUAL_API_URL, settings.ACTUAL_API_KEY)


def get_connection_repo() -> ConnectionRepository:
    return ConnectionRepository(credential_store=get_credential_store())


def get_mapping_repo() -> MappingRepository:
    return MappingRepository()


def get_session_repo() -> SessionRepository:
    return SessionRepository()


def get_import_use_case() -> ImportTransactionsUseCase:
    return ImportTransactionsUseCase(
        fints_port=get_fints_client(),
        actual_port=get_actual_client(),
        credential_store=get_credential_store(),
        session_repo=get_session_repo(),
        mapping_repo=get_mapping_repo(),
        connection_repo=get_connection_repo(),
    )


def get_submit_tan_use_case() -> SubmitTANUseCase:
    return SubmitTANUseCase(
        fints_port=get_fints_client(),
        actual_port=get_actual_client(),
        credential_store=get_credential_store(),
        session_repo=get_session_repo(),
        mapping_repo=get_mapping_repo(),
        connection_repo=get_connection_repo(),
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
```

- [ ] **Step 2: Create Django forms**

`presentation/forms.py`:
```python
from django import forms


class ConnectionForm(forms.Form):
    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "My Bank"}))
    blz = forms.CharField(max_length=8, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "20041133"}))
    url = forms.URLField(widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://banking-dkb.s-fints-pt-dkb.de/fints30"}))
    user_id = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "User ID"}))
    customer_id = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Customer ID (optional)"}))
    pin = forms.CharField(max_length=255, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "PIN"}))


class MappingForm(forms.Form):
    connection_id = forms.IntegerField(widget=forms.HiddenInput())
    bank_account_iban = forms.CharField(max_length=34, widget=forms.TextInput(attrs={"class": "form-control"}))
    actual_budget_id = forms.CharField(max_length=255, widget=forms.Select(attrs={"class": "form-control"}))
    actual_account_id = forms.CharField(max_length=255, widget=forms.Select(attrs={"class": "form-control"}))
    budget_encryption_password = forms.CharField(max_length=255, required=False, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Optional"}))


class ImportForm(forms.Form):
    mapping_id = forms.IntegerField()
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))


class TANForm(forms.Form):
    tan = forms.CharField(max_length=12, widget=forms.TextInput(attrs={"class": "form-control", "style": "letter-spacing: 4px; text-align: center; font-size: 16px;", "placeholder": "Enter TAN", "autofocus": "autofocus"}))
```

- [ ] **Step 3: Create dashboard view**

`presentation/views/dashboard.py`:
```python
from django.shortcuts import render

from presentation.dependency_config import get_connection_repo, get_mapping_repo


def dashboard(request):
    connection_repo = get_connection_repo()
    mapping_repo = get_mapping_repo()
    connections = connection_repo.get_all()
    connections_with_mappings = []
    for conn in connections:
        mappings = mapping_repo.get_by_connection_id(conn.id)
        connections_with_mappings.append({"connection": conn, "mappings": mappings})
    return render(request, "dashboard.html", {"connections_with_mappings": connections_with_mappings})
```

- [ ] **Step 4: Create connection views**

`presentation/views/connections.py`:
```python
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from presentation.dependency_config import get_manage_connections_use_case
from presentation.forms import ConnectionForm


def create_connection(request):
    if request.method == "POST":
        form = ConnectionForm(request.POST)
        if form.is_valid():
            uc = get_manage_connections_use_case()
            uc.create(
                name=form.cleaned_data["name"],
                blz=form.cleaned_data["blz"],
                url=form.cleaned_data["url"],
                user_id=form.cleaned_data["user_id"],
                customer_id=form.cleaned_data.get("customer_id") or None,
                pin=form.cleaned_data["pin"],
            )
            return HttpResponse(status=204, headers={"HX-Refresh": "true"})
    else:
        form = ConnectionForm()
    return render(request, "partials/connection_form.html", {"form": form})


@require_http_methods(["POST"])
def delete_connection(request, connection_id):
    uc = get_manage_connections_use_case()
    uc.delete(connection_id)
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


@require_http_methods(["POST"])
def discover_accounts(request, connection_id):
    uc = get_manage_connections_use_case()
    result = uc.discover_accounts(connection_id)
    if isinstance(result, list):
        import json
        return HttpResponse(json.dumps([{"iban": a.iban, "owner_name": a.owner_name} for a in result]), content_type="application/json")
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})
```

- [ ] **Step 5: Create mapping views**

`presentation/views/mappings.py`:
```python
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from presentation.dependency_config import get_manage_mappings_use_case


def create_mapping(request):
    if request.method == "POST":
        uc = get_manage_mappings_use_case()
        uc.create(
            connection_id=int(request.POST["connection_id"]),
            bank_account_iban=request.POST["bank_account_iban"],
            actual_budget_id=request.POST["actual_budget_id"],
            actual_account_id=request.POST["actual_account_id"],
            budget_encryption_password=request.POST.get("budget_encryption_password") or None,
        )
        return HttpResponse(status=204, headers={"HX-Refresh": "true"})
    return render(request, "partials/mapping_form.html", {"connection_id": request.GET.get("connection_id", "")})


@require_http_methods(["POST"])
def delete_mapping(request, mapping_id):
    uc = get_manage_mappings_use_case()
    uc.delete(mapping_id)
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


def list_budgets(request):
    uc = get_manage_mappings_use_case()
    budgets = uc.list_budgets()
    return JsonResponse([{"sync_id": b.sync_id, "name": b.name} for b in budgets], safe=False)


def list_accounts(request, budget_id):
    uc = get_manage_mappings_use_case()
    pw = request.GET.get("budget_encryption_password")
    accounts = uc.list_accounts_for_budget(budget_id, pw or None)
    return JsonResponse([{"id": a.id, "name": a.name} for a in accounts], safe=False)
```

- [ ] **Step 6: Create import API views**

`presentation/views/import_api.py`:
```python
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from presentation.dependency_config import get_import_use_case, get_submit_tan_use_case
from presentation.forms import ImportForm, TANForm


@require_http_methods(["POST"])
def start_import(request):
    form = ImportForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Invalid form data", status=400)

    uc = get_import_use_case()
    result = uc.execute(
        mapping_id=form.cleaned_data["mapping_id"],
        start_date=form.cleaned_data["start_date"],
        end_date=form.cleaned_data.get("end_date"),
    )
    return render(request, "partials/import_result.html", {"result": result})


@require_http_methods(["POST"])
def submit_tan(request, session_id):
    form = TANForm(request.POST)
    if not form.is_valid():
        return HttpResponse("Invalid TAN", status=400)

    uc = get_submit_tan_use_case()
    result = uc.execute(session_id=session_id, tan=form.cleaned_data["tan"])
    return render(request, "partials/import_result.html", {"result": result})
```

- [ ] **Step 7: Wire up URLs in `presentation/views/__init__.py`**

```python
from django.urls import path

from .connections import create_connection, delete_connection, discover_accounts
from .dashboard import dashboard
from .import_api import start_import, submit_tan
from .mappings import create_mapping, delete_mapping, list_accounts, list_budgets

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
    path("api/imports/<int:session_id>/submit-tan/", submit_tan, name="submit_tan"),
]
```

- [ ] **Step 8: Create templates**

`presentation/templates/dashboard.html`:
```html
{% extends "base.html" %}

{% block title %}FinTS → Actual Importer{% endblock %}

{% block content %}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <h3 style="font-size: 18px;">FinTS → Actual Importer</h3>
    <button class="btn btn-primary" hx-get="/connections/new/" hx-target="#modal-container" hx-swap="innerHTML">+ Add Connection</button>
</div>

<div id="modal-container"></div>

{% for item in connections_with_mappings %}
<div class="card">
    <div class="card-header">
        <div>
            <div class="fw-600" style="font-size: 15px;">{{ item.connection.name }}</div>
            <div class="text-muted text-small">BLZ {{ item.connection.blz }} · User {{ item.connection.user_id }}</div>
        </div>
        <div class="flex gap-2">
            <button class="btn btn-outline btn-sm" hx-post="/connections/{{ item.connection.id }}/discover-accounts/" hx-swap="none">Discover</button>
            <form hx-post="/connections/{{ item.connection.id }}/delete/" hx-swap="none">
                {% csrf_token %}
                <button type="submit" class="btn btn-danger btn-sm">Delete</button>
            </form>
        </div>
    </div>

    {% if item.mappings %}
    <table>
        <thead>
            <tr>
                <th>Bank Account</th>
                <th>→ Actual Account</th>
                <th>Budget</th>
                <th style="text-align: right;">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for mapping in item.mappings %}
            <tr>
                <td>
                    <div class="fw-600">{{ mapping.bank_account_iban }}</div>
                </td>
                <td style="color: #4361ee;">{{ mapping.actual_account_id|truncatechars:12 }}</td>
                <td>
                    {{ mapping.actual_budget_id|truncatechars:16 }}
                    {% if mapping.has_encryption_password %}
                    <span class="text-smaller text-muted">🔒 encrypted</span>
                    {% endif %}
                </td>
                <td style="text-align: right;">
                    <div class="flex gap-2" style="justify-content: flex-end;">
                        <form hx-post="/api/imports/" hx-target="#modal-container" hx-swap="innerHTML">
                            {% csrf_token %}
                            <input type="hidden" name="mapping_id" value="{{ mapping.id }}">
                            <input type="date" name="start_date" value="2024-01-01" style="display:none;">
                            <button type="submit" class="btn btn-primary btn-sm">Import</button>
                        </form>
                        <form hx-post="/mappings/{{ mapping.id }}/delete/" hx-swap="none">
                            {% csrf_token %}
                            <button type="submit" class="btn btn-danger btn-sm">Remove</button>
                        </form>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="card-body text-muted" style="font-size: 13px;">
        No account mappings yet.
        <a href="#" hx-get="/mappings/new/?connection_id={{ item.connection.id }}" hx-target="#modal-container" style="color: #4361ee;">Add mapping</a>
    </div>
    {% endif %}
</div>
{% empty %}
<div class="card">
    <div class="card-body text-center text-muted" style="padding: 40px;">
        No bank connections configured yet.<br>
        <a href="#" hx-get="/connections/new/" hx-target="#modal-container" style="color: #4361ee;">Add your first connection</a>
    </div>
</div>
{% endfor %}
{% endblock %}
```

`presentation/templates/partials/connection_form.html`:
```html
<div class="overlay" id="connection-modal">
    <div class="modal">
        <h3 class="text-center" style="margin-bottom: 20px; font-size: 16px;">Add Bank Connection</h3>
        <form hx-post="/connections/new/" hx-target="#modal-container">
            {% csrf_token %}
            <div class="form-group">
                <label>Name</label>
                {{ form.name }}
            </div>
            <div class="form-group">
                <label>BLZ (Bank Code)</label>
                {{ form.blz }}
            </div>
            <div class="form-group">
                <label>FinTS URL</label>
                {{ form.url }}
            </div>
            <div class="form-group">
                <label>User ID</label>
                {{ form.user_id }}
            </div>
            <div class="form-group">
                <label>Customer ID (optional)</label>
                {{ form.customer_id }}
            </div>
            <div class="form-group">
                <label>PIN</label>
                {{ form.pin }}
            </div>
            <div class="flex gap-2" style="margin-top: 20px;">
                <button type="button" class="btn btn-outline" style="flex:1;" onclick="document.getElementById('connection-modal').remove()">Cancel</button>
                <button type="submit" class="btn btn-primary" style="flex:1;">Save</button>
            </div>
        </form>
    </div>
</div>
```

`presentation/templates/partials/mapping_form.html`:
```html
<div class="overlay" id="mapping-modal">
    <div class="modal">
        <h3 class="text-center" style="margin-bottom: 20px; font-size: 16px;">Add Account Mapping</h3>
        <form hx-post="/mappings/new/" hx-target="#modal-container">
            {% csrf_token %}
            <input type="hidden" name="connection_id" value="{{ connection_id }}">
            <div class="form-group">
                <label>Bank Account IBAN</label>
                <input type="text" name="bank_account_iban" class="form-control" placeholder="DE89 3704 0044 ...">
            </div>
            <div class="form-group">
                <label>Actual Budget</label>
                <select name="actual_budget_id" class="form-control" id="budget-select">
                    <option value="">Loading...</option>
                </select>
            </div>
            <div class="form-group">
                <label>Actual Account</label>
                <select name="actual_account_id" class="form-control" id="account-select">
                    <option value="">Select budget first</option>
                </select>
            </div>
            <div class="form-group">
                <label>Budget Encryption Password (optional)</label>
                <input type="password" name="budget_encryption_password" class="form-control" placeholder="Leave empty if not encrypted">
            </div>
            <div class="flex gap-2" style="margin-top: 20px;">
                <button type="button" class="btn btn-outline" style="flex:1;" onclick="document.getElementById('mapping-modal').remove()">Cancel</button>
                <button type="submit" class="btn btn-primary" style="flex:1;">Save</button>
            </div>
        </form>
        <script>
            fetch('/api/budgets/').then(r=>r.json()).then(budgets=>{
                const sel=document.getElementById('budget-select');
                sel.innerHTML='<option value="">Select budget</option>'+budgets.map(b=>`<option value="${b.sync_id}">${b.name}</option>`).join('');
                sel.onchange=()=>{
                    const pw=document.querySelector('[name=budget_encryption_password]').value;
                    fetch(`/api/budgets/${sel.value}/accounts/${pw?'?budget_encryption_password='+pw:''}`).then(r=>r.json()).then(accounts=>{
                        const asel=document.getElementById('account-select');
                        asel.innerHTML=accounts.map(a=>`<option value="${a.id}">${a.name}</option>`).join('');
                    });
                };
            });
        </script>
    </div>
</div>
```

`presentation/templates/partials/tan_modal.html`:
```html
<div class="overlay" id="tan-modal">
    <div class="modal">
        <div class="text-center" style="margin-bottom: 20px;">
            <div style="width: 48px; height: 48px; background: #fff3cd; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px; font-size: 22px;">🔐</div>
            <h3 style="font-size: 16px;">TAN Required</h3>
        </div>
        <div style="background: #f8f9fa; border-radius: 8px; padding: 14px; margin-bottom: 20px;">
            <div class="text-muted text-smaller" style="text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">Challenge</div>
            <div style="font-size: 13px; line-height: 1.5;">{{ challenge_text }}</div>
        </div>
        <form hx-post="/api/imports/{{ session_id }}/submit-tan/" hx-target="#modal-container">
            {% csrf_token %}
            <div class="form-group">
                <label>TAN</label>
                <input type="text" name="tan" style="width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; text-align: center; letter-spacing: 4px;" placeholder="Enter TAN" autofocus>
            </div>
            <div class="flex gap-2">
                <button type="button" class="btn btn-outline" style="flex:1;" onclick="document.getElementById('tan-modal').remove()">Cancel</button>
                <button type="submit" class="btn btn-primary" style="flex:1;">Submit</button>
            </div>
        </form>
    </div>
</div>
```

`presentation/templates/partials/import_result.html`:
```html
{% if result.status == "tan_required" %}
    {% include "partials/tan_modal.html" with session_id=result.session_id challenge_text=result.challenge_text %}
{% elif result.status == "completed" %}
<div class="overlay" id="result-modal">
    <div class="modal text-center">
        <div style="margin-bottom: 16px;">
            <div style="width: 48px; height: 48px; background: #d4edda; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px; font-size: 22px;">✅</div>
            <h3 style="font-size: 16px;">Import Complete</h3>
        </div>
        <div style="font-size: 14px; color: #666; margin-bottom: 16px;">
            <div>{{ result.imported }} transactions added</div>
            <div>{{ result.updated }} transactions updated</div>
        </div>
        <button class="btn btn-primary" onclick="document.getElementById('result-modal').remove(); location.reload();">OK</button>
    </div>
</div>
{% endif %}
```

- [ ] **Step 9: Verify everything runs**

Run: `python manage.py check && python manage.py runserver`
Expected: Server starts, dashboard renders at localhost:8000.

- [ ] **Step 10: Commit and push**

```bash
git add -A && git commit -m "feat: presentation layer — views, templates, HTMX UI" && git push
```
