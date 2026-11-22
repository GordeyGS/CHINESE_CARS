import os

from django.contrib.staticfiles import finders
from django.template import Context, Template


def test_asset_url_contains_file_version():
    url = Template("{% load assets %}{% asset 'css/site.css' %}").render(Context())

    version = int(os.path.getmtime(finders.find("css/site.css")))
    assert url.endswith(f"css/site.css?v={version}")


def test_unknown_asset_falls_back_to_plain_static_url():
    url = Template("{% load assets %}{% asset 'css/missing.css' %}").render(Context())

    assert url.endswith("css/missing.css")
