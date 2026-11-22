from django import forms

from .models import Modification, Powertrain


class ModificationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, modification):
        generation = modification.generation
        model = generation.model
        return f"{model.brand.name} / {model.name} / {generation.name} / {modification.name}"


def grouped_modification_choices(modifications, empty_label):
    """Short select options grouped by brand: "Seal · Excellence AWD".

    The generation is added only when a model has several generations in the list,
    otherwise it is noise ("Актуальное поколение") that makes the option too long.
    """
    modifications = list(modifications)
    generations_by_model = {}
    for modification in modifications:
        generation = modification.generation
        generations_by_model.setdefault(generation.model_id, set()).add(generation.pk)

    groups = {}
    for modification in modifications:
        generation = modification.generation
        model = generation.model
        label = f"{model.name} · {modification.name}"
        if len(generations_by_model[model.pk]) > 1:
            label += f" ({generation.name})"
        groups.setdefault(model.brand.name, []).append((modification.pk, label))
    return [("", empty_label), *groups.items()]


class ComparisonForm(forms.Form):
    left = ModificationChoiceField(label="Автомобиль 1", queryset=Modification.objects.none())
    right = ModificationChoiceField(label="Автомобиль 2", queryset=Modification.objects.none())

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop("queryset")
        super().__init__(*args, **kwargs)
        choices = grouped_modification_choices(queryset, "Выберите модификацию")
        for field in self.fields.values():
            field.queryset = queryset  # validation still goes through the queryset
            field.choices = choices
            field.widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("left") == cleaned_data.get("right") and cleaned_data.get("left"):
            raise forms.ValidationError("Выберите две разные модификации.")
        return cleaned_data


class CarFilterForm(forms.Form):
    """Validates catalog query-string filters; empty values mean "no filter"."""

    brand = forms.SlugField(required=False)
    body = forms.SlugField(required=False)
    powertrain = forms.ChoiceField(required=False, choices=())
    drive = forms.CharField(required=False, max_length=10)
    market = forms.CharField(required=False, max_length=20)
    min_price = forms.DecimalField(label="Цена от", required=False, min_value=0, max_digits=14, decimal_places=2)
    max_price = forms.DecimalField(label="Цена до", required=False, min_value=0, max_digits=14, decimal_places=2)
    currency = forms.CharField(label="Валюта", required=False, max_length=3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["powertrain"].choices = [("", "Все"), *Powertrain.Type.choices]

    def clean(self):
        cleaned = super().clean()
        minimum = cleaned.get("min_price")
        maximum = cleaned.get("max_price")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("max_price", "Максимальная цена должна быть не меньше минимальной.")
        if (minimum is not None or maximum is not None) and not cleaned.get("currency"):
            self.add_error("currency", "Чтобы фильтровать по цене, выберите валюту: разные валюты не сравниваются.")
        return cleaned
