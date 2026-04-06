from django.db import models

from .fields import EncryptedCharField


class BankConnectionModel(models.Model):
    name = models.CharField(max_length=255)
    blz = models.CharField(max_length=8)
    url = models.URLField()
    user_id = models.CharField(max_length=255)
    customer_id = models.CharField(max_length=255, blank=True, default="")
    pin = EncryptedCharField(max_length=1024)

    class Meta:
        app_label = "persistence"
        db_table = "bank_connections"

    def __str__(self):
        return self.name


class AccountMappingModel(models.Model):
    connection = models.ForeignKey(BankConnectionModel, on_delete=models.CASCADE, related_name="mappings")
    bank_account_iban = models.CharField(max_length=34)
    actual_budget_id = models.CharField(max_length=255)
    actual_account_id = models.CharField(max_length=255)
    budget_encryption_password = EncryptedCharField(max_length=1024, blank=True, default="")

    class Meta:
        app_label = "persistence"
        db_table = "account_mappings"

    def __str__(self):
        return f"{self.bank_account_iban} → {self.actual_account_id}"


class ImportSessionModel(models.Model):
    STATUS_CHOICES = [
        ("tan_required", "TAN Required"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    connection = models.ForeignKey(BankConnectionModel, on_delete=models.CASCADE)
    mapping = models.ForeignKey(AccountMappingModel, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    started_at = models.DateTimeField(auto_now_add=True)
    challenge_text = models.TextField(blank=True, default="")
    client_state_blob = models.BinaryField(null=True, blank=True)
    dialog_state_blob = models.BinaryField(null=True, blank=True)
    tan_state_blob = models.BinaryField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    imported_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)

    class Meta:
        app_label = "persistence"
        db_table = "import_sessions"
