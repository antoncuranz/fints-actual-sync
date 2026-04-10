from domain.entities import AccountMapping

from application.use_cases._export import export_to_actual


def test_export_to_actual_skips_empty_transaction_list():
    mapping = AccountMapping(
        actual_budget_id="budget",
        actual_account_id="account",
        budget_encryption_password="secret",
    )

    class ActualPort:
        def import_transactions(self, *args, **kwargs):
            raise AssertionError("empty export should not call Actual")

    result = export_to_actual([], mapping, ActualPort())

    assert result.status == "completed"
    assert result.imported == 0
    assert result.updated == 0
