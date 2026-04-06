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
        accounts = self._actual.get_accounts(budget_id, budget_encryption_password)
        return [ActualAccountDTO(id=a.id, name=a.name) for a in accounts]

    def _to_dto(self, mapping: AccountMapping) -> AccountMappingDTO:
        return AccountMappingDTO(
            id=mapping.id, connection_id=mapping.connection_id,
            bank_account_iban=mapping.bank_account_iban,
            actual_budget_id=mapping.actual_budget_id,
            actual_account_id=mapping.actual_account_id,
            has_encryption_password=bool(mapping.budget_encryption_password),
        )
