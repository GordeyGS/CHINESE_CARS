from django.urls import path

from . import views

app_name = "knowledge"

urlpatterns = [
    path("articles/", views.article_list, name="article-list"),
    path("articles/<slug:slug>/", views.article_detail, name="article-detail"),
    path("sources/", views.source_list, name="source-list"),
]
