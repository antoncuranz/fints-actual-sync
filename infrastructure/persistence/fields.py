import functools

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


@functools.lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


class EncryptedCharField(models.CharField):
    def get_prep_value(self, value: str | None) -> str:
        if not value:
            return ""
        return _get_fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value: str | None, expression, connection) -> str | None:
        if not value:
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt field value — key mismatch or data corruption") from exc

    def to_python(self, value):
        if not value or not isinstance(value, str):
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return value

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, "infrastructure.persistence.fields.EncryptedCharField", args, kwargs
