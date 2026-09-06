from datetime import date

from django.utils import timezone

from application.use_cases.import_transactions import ImportTransactionsUseCase
from application.use_cases.submit_tan import SubmitTANUseCase
from domain.entities import AccountMapping, BankConnection, ImportSession
from domain.ports import TANChallenge


def test_login_tan_session_preserves_state_for_empty_tan_resume():
    connection = BankConnection(id=1)
    mapping = AccountMapping(id=2, connection_id=connection.id, bank_account_iban="DE001")
    challenge = TANChallenge("Approve login", b"client", b"dialog", b"login-tan", decoupled=True, resume_transaction_fetch=True)
    sessions = SessionRepository()
    fints = FinTSPort(challenge)

    import_result = ImportTransactionsUseCase(
        fints, ActualPort(), object(), sessions, MappingRepository(mapping), ConnectionRepository(connection)
    ).execute(mapping.id, date(2026, 1, 1))
    sessions.session.started_at = timezone.now()

    SubmitTANUseCase(
        fints, ActualPort(), object(), sessions, MappingRepository(mapping), ConnectionRepository(connection), 5
    ).execute(import_result.session_id, "")

    assert fints.submit_args == (connection, b"client", b"dialog", b"login-tan", "", "DE001", date(2026, 1, 1), None, True, True)


def test_submit_tan_persists_repeated_decoupled_challenge():
    connection = BankConnection(id=1)
    mapping = AccountMapping(id=2, connection_id=connection.id, bank_account_iban="DE001")
    sessions = SessionRepository()
    session = sessions.save(ImportSession(
        connection_id=connection.id,
        mapping_id=mapping.id,
        started_at=timezone.now(),
        challenge_text="Approve in Consorsbank app",
        client_state_blob=b"client",
        dialog_state_blob=b"dialog",
        tan_state_blob=b"first-tan",
        decoupled=True,
    ))
    fints = FinTSPort(_decoupled_challenge(b"next-tan"))
    fints.submit_result = fints.challenge

    SubmitTANUseCase(
        fints, ActualPort(), object(), sessions, MappingRepository(mapping), ConnectionRepository(connection), 5
    ).execute(session.id, "")

    assert fints.submit_args[4] == ""
    assert getattr(sessions.session, "decoupled", False) is True
    assert sessions.session.tan_state_blob == b"next-tan"


def test_submit_tan_accepts_timezone_aware_session_start_time():
    connection = BankConnection(id=1)
    mapping = AccountMapping(id=2, connection_id=connection.id, bank_account_iban="DE001")
    sessions = SessionRepository()
    session = sessions.save(ImportSession(
        connection_id=connection.id,
        mapping_id=mapping.id,
        started_at=timezone.now(),
        challenge_text="Approve in Consorsbank app",
        client_state_blob=b"client",
        dialog_state_blob=b"dialog",
        tan_state_blob=b"first-tan",
        decoupled=True,
    ))
    fints = FinTSPort(_decoupled_challenge(b"next-tan"))
    fints.submit_result = fints.challenge

    SubmitTANUseCase(
        fints, ActualPort(), object(), sessions, MappingRepository(mapping), ConnectionRepository(connection), 5
    ).execute(session.id, "")

    assert fints.submit_args is not None


def _decoupled_challenge(tan_state_blob):
    challenge = TANChallenge("Approve in Consorsbank app", b"next-client", b"next-dialog", tan_state_blob)
    challenge.decoupled = True
    return challenge


class FinTSPort:
    def __init__(self, challenge):
        self.challenge = challenge
        self.submit_args = None

    def fetch_transactions(self, *args):
        return self.challenge

    def submit_tan(self, *args):
        self.submit_args = args
        return getattr(self, "submit_result", [])


class SessionRepository:
    def __init__(self):
        self.session = None

    def save(self, session):
        session.id = 3
        self.session = session
        return session

    def get_by_id(self, session_id):
        assert session_id == self.session.id
        return self.session

    def delete(self, session_id):
        assert session_id == self.session.id


class MappingRepository:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_by_id(self, mapping_id):
        assert mapping_id == self.mapping.id
        return self.mapping


class ConnectionRepository:
    def __init__(self, connection):
        self.connection = connection

    def get_by_id(self, connection_id):
        assert connection_id == self.connection.id
        return self.connection


class ActualPort:
    def import_transactions(self, *args):
        raise AssertionError("empty transactions must not be exported")
