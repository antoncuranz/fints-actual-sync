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
