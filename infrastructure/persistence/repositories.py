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
