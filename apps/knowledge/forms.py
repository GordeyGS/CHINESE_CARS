from django import forms

from .models import ArticleComment


class CommentForm(forms.ModelForm):
    class Meta:
        model = ArticleComment
        fields = ["body"]
        labels = {"body": "Ваш комментарий"}
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 4, "class": "form-control", "maxlength": ArticleComment.MAX_LENGTH}
            )
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 3:
            raise forms.ValidationError("Комментарий должен содержать хотя бы 3 символа.")
        return body
