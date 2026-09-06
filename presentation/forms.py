from django import forms


class ConnectionForm(forms.Form):
    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "My Bank"}))
    blz = forms.CharField(max_length=8, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "20041133"}))
    url = forms.URLField(widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://banking-dkb.s-fints-pt-dkb.de/fints30"}))
    user_id = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "User ID"}))
    customer_id = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Customer ID (optional)"}))
    pin = forms.CharField(max_length=255, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "PIN"}))


class MappingForm(forms.Form):
    connection_id = forms.IntegerField(widget=forms.HiddenInput())
    bank_account_iban = forms.CharField(max_length=34, widget=forms.TextInput(attrs={"class": "form-control"}))
    actual_budget_id = forms.CharField(max_length=255, widget=forms.Select(attrs={"class": "form-control"}))
    actual_account_id = forms.CharField(max_length=255, widget=forms.Select(attrs={"class": "form-control"}))
    budget_encryption_password = forms.CharField(max_length=255, required=False, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Optional"}))


class ImportForm(forms.Form):
    mapping_id = forms.IntegerField()
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))


class TANForm(forms.Form):
    tan = forms.CharField(max_length=12, widget=forms.TextInput(attrs={"class": "form-control", "style": "letter-spacing: 4px; text-align: center; font-size: 16px;", "placeholder": "Enter TAN", "autofocus": "autofocus"}))

    def __init__(self, *args, decoupled=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tan"].required = not decoupled


class WebhookConfigForm(forms.Form):
    url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://hooks.example.com/trigger"}),
    )
    body_template = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": '{"event": "$event", "session_id": "$session_id"}'}),
    )
    method = forms.ChoiceField(
        choices=[("POST", "POST"), ("PUT", "PUT")],
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    headers = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": '{"Authorization": "Bearer xxx"}'}),
    )
    enabled = forms.BooleanField(required=False)
