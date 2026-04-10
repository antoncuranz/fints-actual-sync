import datetime
import logging

from fints.client import FinTS3PinTanClient, NeedTANResponse

from domain.entities import BankAccount, BankConnection, NormalizedTransaction
from domain.exceptions import FinTSAuthenticationError, FinTSConnectionError
from domain.ports import TANChallenge

logger = logging.getLogger(__name__)


class FinTSClientAdapter:
    def __init__(self, product_id: str, product_version: str):
        self.product_id = product_id
        self.product_version = product_version

    def _create_client(self, connection: BankConnection, from_data: bytes | None = None) -> FinTS3PinTanClient:
        return FinTS3PinTanClient(
            bank_identifier=connection.blz,
            user_id=connection.user_id,
            pin=connection.pin,
            server=connection.url,
            customer_id=connection.customer_id or connection.user_id,
            force_twostep_tan={"HKKAZ", "HKCAZ"},
            product_id=self.product_id,
            product_version=self.product_version,
            from_data=from_data,
        )

    def _handle_fints_error(self, exc: Exception, context: str) -> None:
        msg = str(exc).lower()
        if any(kw in msg for kw in ("auth", "pin", "password", "locked", "9050", "9931")):
            raise FinTSAuthenticationError(f"{context}: {exc}") from exc
        raise FinTSConnectionError(f"{context}: {exc}") from exc

    def fetch_accounts(self, connection: BankConnection) -> list[BankAccount]:
        client = self._create_client(connection)
        try:
            with client:
                sepa_accounts = client.get_sepa_accounts()
                info = client.get_information()
                accounts_info = {a["iban"]: a for a in info.get("accounts", [])}
                result = []
                for sa in sepa_accounts:
                    detail = accounts_info.get(sa.iban, {})
                    result.append(BankAccount(
                        iban=sa.iban,
                        account_number=sa.accountnumber,
                        bank_identifier=str(sa.bic) if sa.bic else "",
                        currency=detail.get("currency", "EUR"),
                        owner_name=", ".join(detail.get("owner_name", [""])),
                        account_type=str(detail.get("type", "")),
                    ))
                return result
        except (FinTSConnectionError, FinTSAuthenticationError):
            raise
        except Exception as exc:
            self._handle_fints_error(exc, "fetch_accounts failed")

    def fetch_transactions(
        self,
        connection: BankConnection,
        iban: str,
        start_date: datetime.date,
        end_date: datetime.date | None,
    ) -> list[NormalizedTransaction] | TANChallenge:
        client = self._create_client(connection)
        logger.debug(
            "fints_fetch start connection_id=%s iban_suffix=%s start_date=%s end_date=%s",
            connection.id,
            iban[-4:],
            start_date,
            end_date,
        )
        try:
            with client:
                accounts = client.get_sepa_accounts()
                logger.debug("fints_fetch sepa_account_count=%s", len(accounts))
                account = next((a for a in accounts if a.iban == iban), None)
                if account is None:
                    raise ValueError(f"No SEPA account found for IBAN {iban}")
                result = client.get_transactions(account, start_date, end_date)
                logger.debug("fints_fetch raw_result_type=%s", type(result).__name__)

                if isinstance(result, NeedTANResponse):
                    logger.debug("fints_fetch tan_required")
                    return TANChallenge(
                        challenge_text=result.challenge or "Please enter TAN",
                        client_state_blob=client.deconstruct(including_private=True),
                        dialog_state_blob=client.pause_dialog(),
                        tan_state_blob=result.get_data(),
                    )
        except (FinTSConnectionError, FinTSAuthenticationError, ValueError):
            raise
        except Exception as exc:
            self._handle_fints_error(exc, "fetch_transactions failed")

        normalized = [self._normalize(tx) for tx in result]
        logger.debug(
            "fints_fetch normalized_count=%s first_transaction=%s",
            len(normalized),
            {
                "date": normalized[0].date,
                "amount": normalized[0].amount,
                "imported_id": normalized[0].imported_id,
            } if normalized else None,
        )
        return normalized

    def submit_tan(
        self,
        connection: BankConnection,
        client_state: bytes,
        dialog_state: bytes,
        tan_state: bytes,
        tan: str,
    ) -> list[NormalizedTransaction] | TANChallenge:
        client = self._create_client(connection, from_data=client_state)
        challenge = NeedTANResponse.from_data(tan_state)
        try:
            with client.resume_dialog(dialog_state):
                result = client.send_tan(challenge, tan)
                logger.debug("fints_submit_tan raw_result_type=%s", type(result).__name__)

                if isinstance(result, NeedTANResponse):
                    logger.debug("fints_submit_tan tan_required")
                    return TANChallenge(
                        challenge_text=result.challenge or "Please enter TAN",
                        client_state_blob=client.deconstruct(including_private=True),
                        dialog_state_blob=client.pause_dialog(),
                        tan_state_blob=result.get_data(),
                    )
        except (FinTSConnectionError, FinTSAuthenticationError):
            raise
        except Exception as exc:
            self._handle_fints_error(exc, "submit_tan failed")

        normalized = [self._normalize(tx) for tx in result]
        logger.debug(
            "fints_submit_tan normalized_count=%s first_transaction=%s",
            len(normalized),
            {
                "date": normalized[0].date,
                "amount": normalized[0].amount,
                "imported_id": normalized[0].imported_id,
            } if normalized else None,
        )
        return normalized

    def _normalize(self, tx) -> NormalizedTransaction:
        data = tx.data if hasattr(tx, "data") else {}
        if hasattr(data, "data"):
            data = data.data

        amount = data.get("amount", 0)
        if hasattr(amount, "amount"):
            amount_val = int(round(amount.amount * 100))
        else:
            amount_val = int(round(float(str(amount).replace(",", ".")) * 100))

        date_str = ""
        raw_date = data.get("date")
        if raw_date is not None:
            date_str = raw_date.isoformat() if hasattr(raw_date, "isoformat") else str(raw_date)

        applicant_name = data.get("applicant_name", "") or ""
        purpose = data.get("purpose", "") or ""
        bank_ref = data.get("bank_reference", "") or data.get("transaction_id", "") or ""

        return NormalizedTransaction(
            date=date_str,
            amount=amount_val,
            payee_name=applicant_name,
            imported_payee=applicant_name,
            imported_id=bank_ref,
            notes=purpose,
            cleared=True,
        )
