from django.urls import path

from . import views

app_name = "knowledge"

urlpatterns = [
    path("articles/", views.article_list, name="article-list"),
    path("articles/<slug:slug>/", views.article_detail, name="article-detail"),
    path("articles/<slug:slug>/comments/", views.add_comment, name="comment-add"),
    path("articles/<slug:slug>/comments/<int:comment_id>/delete/", views.delete_comment, name="comment-delete"),
    path("sources/", views.source_list, name="source-list"),
]
