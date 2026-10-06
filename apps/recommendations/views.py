from django.shortcuts import render

from .forms import RecommendationForm
from .services import RecommendationEngine


def recommendations(request):
    is_submitted = bool(request.GET)
    form = RecommendationForm(request.GET if is_submitted else None)
    context = {"form": form, "is_submitted": is_submitted}
    if is_submitted and form.is_valid():
        results, has_exact_matches = RecommendationEngine(form.cleaned_data).recommend()
        context.update({"results": results, "has_exact_matches": has_exact_matches})
    return render(request, "recommendations/index.html", context)
