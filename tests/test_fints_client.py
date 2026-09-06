from datetime import date
from types import SimpleNamespace

from domain.entities import BankConnection
from domain.ports import TANChallenge
from infrastructure.fints.client import FinTSClientAdapter


def test_create_client_forces_two_step_tan_for_transaction_fetch(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("infrastructure.fints.client.FinTS3PinTanClient", FakeClient)

    connection = BankConnection(
        blz="12345678",
        user_id="user",
        customer_id="customer",
        pin="pin",
        url="https://bank.example",
    )

    adapter = FinTSClientAdapter(product_id="product", product_version="1.0")
    adapter._create_client(connection)

    assert captured["force_twostep_tan"] == {"HKKAZ", "HKSAL"}


def test_fetch_transactions_selects_consorsbank_901_mechanism(monkeypatch):
    clients = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.init_tan_response = None
            self.selected_mechanism = None
            self.fetched_tan_mechanisms = False
            self.account = SimpleNamespace(iban="DE001")
            clients.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_tan_mechanisms(self):
            return {"900": object(), "901": object()}

        def get_current_tan_mechanism(self):
            return None

        def fetch_tan_mechanisms(self):
            self.fetched_tan_mechanisms = True

        def set_tan_mechanism(self, mechanism):
            self.selected_mechanism = mechanism

        def get_sepa_accounts(self):
            return [self.account]

        def get_transactions(self, *args):
            return []

    monkeypatch.setattr("infrastructure.fints.client.FinTS3PinTanClient", FakeClient)

    adapter = FinTSClientAdapter(product_id="product", product_version="1.0")
    adapter.fetch_transactions(_connection(), "DE001", date(2026, 1, 1), None)

    assert clients[0].selected_mechanism == "901"
    assert clients[0].fetched_tan_mechanisms is True


def test_fetch_transactions_defers_initial_login_tan_before_transaction_fetch(monkeypatch):
    class FakeNeedTANResponse:
        challenge = "Approve login"
        decoupled = False

        def get_data(self):
            return b"login-tan"

    class FakeClient:
        def __init__(self, **kwargs):
            self.init_tan_response = FakeNeedTANResponse()
            self.get_transactions_calls = 0
            self.account = SimpleNamespace(iban="DE001")
            self.selected_mechanism = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_tan_mechanisms(self):
            return {"901": object()}

        def get_current_tan_mechanism(self):
            return "901"

        def set_tan_mechanism(self, mechanism):
            self.selected_mechanism = mechanism

        def get_sepa_accounts(self):
            return [self.account]

        def get_transactions(self, *args):
            self.get_transactions_calls += 1
            return []

        def deconstruct(self, **kwargs):
            return b"client"

        def pause_dialog(self):
            return b"dialog"

    client = FakeClient()
    monkeypatch.setattr("infrastructure.fints.client.FinTS3PinTanClient", lambda **kwargs: client)
    monkeypatch.setattr("infrastructure.fints.client.NeedTANResponse", FakeNeedTANResponse)

    adapter = FinTSClientAdapter(product_id="product", product_version="1.0")
    result = adapter.fetch_transactions(_connection(), "DE001", date(2026, 1, 1), None)

    assert isinstance(result, TANChallenge)
    assert result.challenge_text == "Approve login"
    assert result.tan_state_blob == b"login-tan"
    assert client.get_transactions_calls == 0


def test_fetch_transactions_marks_decoupled_tan_challenge_for_empty_tan_continuation(monkeypatch):
    class FakeNeedTANResponse:
        challenge = "Approve in Consorsbank app"
        decoupled = True

        def get_data(self):
            return b"decoupled-tan"

    class FakeClient:
        def __init__(self, **kwargs):
            self.init_tan_response = None
            self.account = SimpleNamespace(iban="DE001")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_tan_mechanisms(self):
            return {"901": object()}

        def get_current_tan_mechanism(self):
            return "901"

        def set_tan_mechanism(self, mechanism):
            pass

        def get_sepa_accounts(self):
            return [self.account]

        def get_transactions(self, *args):
            return FakeNeedTANResponse()

        def deconstruct(self, **kwargs):
            return b"client"

        def pause_dialog(self):
            return b"dialog"

    monkeypatch.setattr("infrastructure.fints.client.FinTS3PinTanClient", FakeClient)
    monkeypatch.setattr("infrastructure.fints.client.NeedTANResponse", FakeNeedTANResponse)

    adapter = FinTSClientAdapter(product_id="product", product_version="1.0")
    result = adapter.fetch_transactions(_connection(), "DE001", date(2026, 1, 1), None)

    assert isinstance(result, TANChallenge)
    assert getattr(result, "decoupled", False) is True


def test_submit_tan_resumes_typed_login_fetch_with_persisted_request(monkeypatch):
    start_date = date(2026, 1, 1)
    end_date = date(2026, 1, 31)

    class FakeNeedTANResponse:
        request_iban = "DE001"
        request_start_date = start_date
        request_end_date = end_date

        @classmethod
        def from_data(cls, data):
            assert data == b"typed-login-tan"
            return cls()

    class FakeClient:
        def __init__(self, **kwargs):
            self.account = SimpleNamespace(iban="DE001")
            self.get_transactions_args = None

        def resume_dialog(self, dialog_state):
            assert dialog_state == b"dialog"
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send_tan(self, challenge, tan):
            assert tan == "123456"
            return []

        def get_sepa_accounts(self):
            return [self.account]

        def get_transactions(self, *args):
            self.get_transactions_args = args
            return []

    client = FakeClient()
    monkeypatch.setattr("infrastructure.fints.client.FinTS3PinTanClient", lambda **kwargs: client)
    monkeypatch.setattr("infrastructure.fints.client.NeedTANResponse", FakeNeedTANResponse)

    adapter = FinTSClientAdapter(product_id="product", product_version="1.0")
    result = adapter.submit_tan(
        _connection(), b"client", b"dialog", b"typed-login-tan", "123456", "DE001", start_date, end_date, True, False
    )

    assert result == []
    assert client.get_transactions_args == (client.account, start_date, end_date)


def test_submit_tan_returns_updated_decoupled_challenge_after_empty_poll(monkeypatch):
    class FakeNeedTANResponse:
        challenge = "Approve in Consorsbank app"

        def __init__(self, decoupled=True):
            self.decoupled = decoupled

        @classmethod
        def from_data(cls, data):
            assert data == b"first-tan"
            return cls(decoupled=False)

        def get_data(self):
            return b"next-tan"

    class FakeClient:
        def __init__(self, **kwargs):
            self.tan = None

        def resume_dialog(self, dialog_state):
            assert dialog_state == b"dialog"
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send_tan(self, challenge, tan):
            self.tan = tan
            assert challenge.decoupled is True
            return FakeNeedTANResponse()

        def deconstruct(self, **kwargs):
            return b"next-client"

        def pause_dialog(self):
            return b"next-dialog"

    client = FakeClient()
    monkeypatch.setattr("infrastructure.fints.client.FinTS3PinTanClient", lambda **kwargs: client)
    monkeypatch.setattr("infrastructure.fints.client.NeedTANResponse", FakeNeedTANResponse)

    adapter = FinTSClientAdapter(product_id="product", product_version="1.0")
    result = adapter.submit_tan(
        _connection(), b"client", b"dialog", b"first-tan", "", "DE001", date(2026, 1, 1), None, False, True
    )

    assert client.tan == ""
    assert isinstance(result, TANChallenge)
    assert getattr(result, "decoupled", False) is True
    assert result.tan_state_blob == b"next-tan"


def _connection():
    return BankConnection(
        id=1,
        blz="12345678",
        user_id="user",
        customer_id="customer",
        pin="pin",
        url="https://bank.example",
    )


def test_normalize_marks_fints_transactions_as_cleared():
    adapter = FinTSClientAdapter(product_id="product", product_version="1.0")

    tx = SimpleNamespace(data={
        "amount": "12.34",
        "date": "2026-04-10",
        "applicant_name": "ACME GmbH",
        "purpose": "Invoice",
        "bank_reference": "ref-123",
    })

    normalized = adapter._normalize(tx)

    assert normalized.cleared is True
