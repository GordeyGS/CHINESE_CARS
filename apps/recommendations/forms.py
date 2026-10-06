from django import forms

from apps.cars.models import BodyType, DriveType, DriverAssistanceSystem, Market, Powertrain, Technology, TrimLevel


class RecommendationForm(forms.Form):
    body_type = forms.ModelChoiceField(label="Тип кузова", queryset=BodyType.objects.none(), required=False, empty_label="Любой")
    powertrain_type = forms.ChoiceField(label="Тип силовой установки", choices=(), required=False)
    drive_type = forms.ModelChoiceField(label="Привод", queryset=DriveType.objects.none(), required=False, empty_label="Любой")
    market = forms.ModelChoiceField(label="Рынок", queryset=Market.objects.none(), required=False, empty_label="Любой")
    min_price = forms.DecimalField(label="Цена от", min_value=0, required=False)
    max_price = forms.DecimalField(label="Цена до", min_value=0, required=False)
    currency = forms.ChoiceField(label="Валюта бюджета", choices=(), required=False)
    min_power_kw = forms.DecimalField(label="Мощность не менее, кВт", min_value=0, required=False)
    min_battery_kwh = forms.DecimalField(label="Батарея не менее, кВт·ч", min_value=0, required=False)
    technology = forms.ModelChoiceField(label="Желаемая технология", queryset=Technology.objects.none(), required=False, empty_label="Не выбрана")
    adas = forms.ModelChoiceField(label="Желаемая система ADAS", queryset=DriverAssistanceSystem.objects.none(), required=False, empty_label="Не выбрана")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body_type"].queryset = BodyType.objects.filter(generations__modifications__is_active=True).distinct()
        self.fields["drive_type"].queryset = DriveType.objects.filter(powertrains__modifications__is_active=True).distinct()
        self.fields["market"].queryset = Market.objects.filter(modification_offers__modification__is_active=True).distinct()
        self.fields["technology"].queryset = Technology.objects.filter(is_active=True)
        self.fields["adas"].queryset = DriverAssistanceSystem.objects.filter(is_active=True)
        self.fields["powertrain_type"].choices = [("", "Любой"), *Powertrain.Type.choices]
        currencies = TrimLevel.objects.filter(is_active=True).exclude(currency_code="").values_list("currency_code", flat=True).distinct().order_by("currency_code")
        self.fields["currency"].choices = [("", "Выберите валюту"), *((code, code) for code in currencies)]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        cleaned = super().clean()
        minimum = cleaned.get("min_price")
        maximum = cleaned.get("max_price")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("max_price", "Максимальная цена должна быть не меньше минимальной.")
        if minimum is not None or maximum is not None:
            if not cleaned.get("market"):
                self.add_error("market", "Для бюджета выберите рынок, чтобы цены были сопоставимы.")
            if not cleaned.get("currency"):
                self.add_error("currency", "Для бюджета выберите валюту.")
        return cleaned
