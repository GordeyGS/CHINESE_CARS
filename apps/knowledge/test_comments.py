import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from .models import Article, ArticleComment, Category, Tag


pytestmark = pytest.mark.django_db
SLUG = "blade-battery-overview"


@pytest.fixture(autouse=True)
def demo_data(db):
    call_command("load_demo_data", verbosity=0)


@pytest.fixture
def reader():
    return get_user_model().objects.create_user(username="reader", password="safe-test-password")


def article_url():
    return reverse("knowledge:article-detail", args=[SLUG])


def test_guest_sees_comments_but_must_log_in_to_post(client, reader):
    ArticleComment.objects.create(article=Article.objects.get(slug=SLUG), author=reader, body="Полезная статья")

    page = client.get(article_url()).content.decode()
    post = client.post(reverse("knowledge:comment-add", args=[SLUG]), {"body": "Гость пишет"})

    assert "Полезная статья" in page
    assert "Войдите" in page and "<textarea" not in page
    assert post.status_code == 302 and reverse("users:login") in post.url
    assert ArticleComment.objects.count() == 1


def test_user_adds_comment_and_text_is_escaped(client, reader):
    client.force_login(reader)

    response = client.post(reverse("knowledge:comment-add", args=[SLUG]), {"body": "  <script>alert(1)</script> ok  "})
    comment = ArticleComment.objects.get()
    page = client.get(article_url()).content.decode()

    assert response.status_code == 302 and response.url.endswith(f"#comment-{comment.pk}")
    assert comment.author == reader and comment.body == "<script>alert(1)</script> ok"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page


def test_too_short_comment_shows_error(client, reader):
    client.force_login(reader)

    response = client.post(reverse("knowledge:comment-add", args=[SLUG]), {"body": " a "})

    assert response.status_code == 200
    assert "хотя бы 3 символа" in response.content.decode()
    assert not ArticleComment.objects.exists()


def test_comments_only_on_published_articles(client, reader):
    Article.objects.filter(slug=SLUG).update(status=Article.Status.DRAFT)
    client.force_login(reader)

    response = client.post(reverse("knowledge:comment-add", args=[SLUG]), {"body": "Черновик"})

    assert response.status_code == 404


def test_hidden_comment_is_not_shown(client, reader):
    ArticleComment.objects.create(article=Article.objects.get(slug=SLUG), author=reader, body="Скрытый текст", is_visible=False)

    assert "Скрытый текст" not in client.get(article_url()).content.decode()


def test_only_author_can_delete_comment(client, reader):
    other = get_user_model().objects.create_user(username="other", password="safe-test-password")
    comment = ArticleComment.objects.create(article=Article.objects.get(slug=SLUG), author=reader, body="Мой комментарий")
    url = reverse("knowledge:comment-delete", args=[SLUG, comment.pk])

    client.force_login(other)
    assert client.post(url).status_code == 404
    client.force_login(reader)
    assert client.get(url).status_code == 405
    assert client.post(url).status_code == 302
    assert not ArticleComment.objects.exists()


def test_article_list_filters_by_tag_and_category(client):
    article = Article.objects.get(slug=SLUG)
    other = Article.objects.exclude(slug=SLUG).filter(status="published").first()
    tag = Tag.objects.create(name="Безопасность", slug="safety")
    article.tags.add(tag)
    category = Category.objects.create(name="История", slug="history")
    Article.objects.filter(pk=other.pk).update(category=category)

    by_tag = client.get(reverse("knowledge:article-list"), {"tag": "safety"})
    by_category = client.get(reverse("knowledge:article-list"), {"category": "history"})
    unknown = client.get(reverse("knowledge:article-list"), {"tag": "missing"})

    assert [a.slug for a in by_tag.context["articles"]] == [SLUG]
    assert [a.slug for a in by_category.context["articles"]] == [other.slug]
    assert unknown.context["active_tag"] is None
    assert unknown.context["page_obj"].paginator.count == Article.objects.filter(status="published").count()
    assert "#Безопасность" in by_tag.content.decode()


def test_draft_articles_do_not_count_in_tag_filter(client):
    tag = Tag.objects.create(name="Черновое", slug="draft-only")
    article = Article.objects.get(slug=SLUG)
    article.tags.add(tag)
    Article.objects.filter(pk=article.pk).update(status=Article.Status.DRAFT)

    response = client.get(reverse("knowledge:article-list"))

    assert tag not in list(response.context["tags"])
