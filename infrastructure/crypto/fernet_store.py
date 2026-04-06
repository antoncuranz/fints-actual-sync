from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from domain.ports import CredentialStore


class FernetCredentialStore:
    def __init__(self):
        try:
            self._fernet = Fernet(settings.FERNET_KEY.encode())
        except Exception as exc:
            raise ValueError(f"Invalid FERNET_KEY: {exc}") from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt: invalid token or wrong key") from exc
