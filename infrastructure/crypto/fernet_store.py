from cryptography.fernet import Fernet
from django.conf import settings

from domain.ports import CredentialStore


class FernetCredentialStore:
    def __init__(self):
        self._fernet = Fernet(settings.FERNET_KEY.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
