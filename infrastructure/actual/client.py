import httpx

from domain.entities import NormalizedTransaction
from domain.exceptions import ActualExportError
from domain.ports import ActualAccount, ActualBudget, ImportResult


class ActualClientAdapter:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/") + "/v1"
        self._client = httpx.Client(headers={"X-API-Key": api_key}, timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def import_transactions(
        self,
        budget_id: str,
        account_id: str,
        transactions: list[NormalizedTransaction],
        budget_encryption_password: str | None,
    ) -> ImportResult:
        headers = {}
        if budget_encryption_password:
            headers["budget-encryption-password"] = budget_encryption_password

        payload = {"transactions": [self._serialize(tx) for tx in transactions]}
        try:
            resp = self._client.post(
                f"{self._base_url}/budgets/{budget_id}/accounts/{account_id}/transactions/import",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ActualExportError(f"Import failed: {exc.response.status_code} — {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise ActualExportError(f"Import request failed: {exc}") from exc

        data = resp.json()["data"]
        return ImportResult(added=data.get("added", []), updated=data.get("updated", []))

    def get_accounts(self, budget_id: str, budget_encryption_password: str | None) -> list[ActualAccount]:
        headers = {}
        if budget_encryption_password:
            headers["budget-encryption-password"] = budget_encryption_password
        try:
            resp = self._client.get(f"{self._base_url}/budgets/{budget_id}/accounts", headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ActualExportError(f"Get accounts failed: {exc.response.status_code} — {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise ActualExportError(f"Get accounts request failed: {exc}") from exc

        return [ActualAccount(id=a["id"], name=a["name"]) for a in resp.json().get("data", [])]

    def get_budgets(self) -> list[ActualBudget]:
        try:
            resp = self._client.get(f"{self._base_url}/budgets")
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ActualExportError(f"Get budgets failed: {exc.response.status_code} — {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise ActualExportError(f"Get budgets request failed: {exc}") from exc

        return [
            ActualBudget(sync_id=b.get("groupId", ""), name=b.get("name", ""))
            for b in resp.json().get("data", [])
        ]

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
