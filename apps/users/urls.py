from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .forms import LoginForm

app_name = "users"

urlpatterns = [
    path("login/", LoginView.as_view(template_name="users/login.html", authentication_form=LoginForm), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("favorites/", views.favorites, name="favorites"),
    path("favorites/articles/<slug:slug>/", views.toggle_favorite_article, name="favorite-article"),
    path("favorites/models/<slug:slug>/", views.toggle_favorite_model, name="favorite-model"),
]
