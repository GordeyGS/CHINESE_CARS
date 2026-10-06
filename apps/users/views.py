from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import RegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Регистрация завершена. Добро пожаловать!")
        return redirect("core:home")
    return render(request, "users/register.html", {"form": form})
