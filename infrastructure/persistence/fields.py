from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


class EncryptedCharField(models.CharField):
    def _get_fernet(self) -> Fernet:
        return Fernet(settings.FERNET_KEY.encode())

    def get_prep_value(self, value: str | None) -> str:
        if not value:
            return ""
        return self._get_fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value: str | None, expression, connection) -> str | None:
        if not value:
            return value
        return self._get_fernet().decrypt(value.encode()).decode()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, "infrastructure.persistence.fields.EncryptedCharField", args, kwargs
