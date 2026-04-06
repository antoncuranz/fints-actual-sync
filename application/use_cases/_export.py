from application.dto import ImportResultDTO


def export_to_actual(transactions, mapping, actual_port) -> ImportResultDTO:
    for tx in transactions:
        tx.account = mapping.actual_account_id
    budget_pw = mapping.budget_encryption_password
    result = actual_port.import_transactions(mapping.actual_budget_id, mapping.actual_account_id, transactions, budget_pw)
    return ImportResultDTO(status="completed", imported=len(result.added), updated=len(result.updated))
