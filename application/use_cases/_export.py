import logging

from application.dto import ImportResultDTO


logger = logging.getLogger(__name__)


def export_to_actual(transactions, mapping, actual_port) -> ImportResultDTO:
    logger.debug(
        "export_to_actual transaction_count=%s budget_id=%s account_id=%s first_transaction=%s",
        len(transactions),
        mapping.actual_budget_id,
        mapping.actual_account_id,
        {
            "date": transactions[0].date,
            "amount": transactions[0].amount,
            "imported_id": transactions[0].imported_id,
        } if transactions else None,
    )
    for tx in transactions:
        tx.account = mapping.actual_account_id
    budget_pw = mapping.budget_encryption_password
    result = actual_port.import_transactions(mapping.actual_budget_id, mapping.actual_account_id, transactions, budget_pw)
    logger.debug("export_to_actual imported=%s updated=%s", len(result.added), len(result.updated))
    return ImportResultDTO(status="completed", imported=len(result.added), updated=len(result.updated))
