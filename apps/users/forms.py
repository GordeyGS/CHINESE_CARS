from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class BootstrapFormMixin:
    def _apply_bootstrap(self):
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
