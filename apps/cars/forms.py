from django import forms

from .models import Modification


class ModificationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, modification):
        generation = modification.generation
        model = generation.model
        return f"{model.brand.name} / {model.name} / {generation.name} / {modification.name}"


class ComparisonForm(forms.Form):
    left = ModificationChoiceField(label="Автомобиль 1", queryset=Modification.objects.none())
    right = ModificationChoiceField(label="Автомобиль 2", queryset=Modification.objects.none())

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop("queryset")
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.queryset = queryset
            field.empty_label = "Выберите модификацию"
            field.widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("left") == cleaned_data.get("right") and cleaned_data.get("left"):
            raise forms.ValidationError("Выберите две разные модификации.")
        return cleaned_data
