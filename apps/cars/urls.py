from django.urls import path

from . import views

app_name = "cars"

urlpatterns = [
    path("compare/", views.compare, name="compare"),
    path("brands/", views.brand_list, name="brand-list"),
    path("brands/<slug:slug>/", views.brand_detail, name="brand-detail"),
    path("cars/", views.car_list, name="model-list"),
    path("cars/modifications/<slug:slug>/", views.modification_detail, name="modification-detail"),
    path("cars/<slug:slug>/", views.model_detail, name="model-detail"),
    path("technologies/", views.technology_list, name="technology-list"),
    path("technologies/<slug:slug>/", views.technology_detail, name="technology-detail"),
]
