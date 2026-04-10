from types import SimpleNamespace

from domain.entities import BankConnection
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

    assert captured["force_twostep_tan"] == {"HKKAZ", "HKCAZ"}


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
