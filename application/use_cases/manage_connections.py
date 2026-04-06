from application.dto import BankAccountDTO, BankConnectionDTO, TANRequiredDTO
from domain.entities import BankConnection
from domain.ports import ConnectionRepository, CredentialStore, FinTSClientPort, TANChallenge


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
        result = self._fints.fetch_accounts(connection)
        if isinstance(result, TANChallenge):
            return TANRequiredDTO(session_id=0, challenge_text=result.challenge_text)
        return [BankAccountDTO(iban=a.iban, account_number=a.account_number, currency=a.currency, owner_name=a.owner_name, account_type=a.account_type) for a in result]

    def _to_dto(self, connection: BankConnection) -> BankConnectionDTO:
        return BankConnectionDTO(
            id=connection.id, name=connection.name, blz=connection.blz,
            url=connection.url, user_id=connection.user_id, customer_id=connection.customer_id,
        )
