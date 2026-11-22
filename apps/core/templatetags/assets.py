"""{% asset 'css/site.css' %} — a static URL with the file version for cache busting.

Static files are served without hashed names, so a browser may keep an old
stylesheet after it was changed. The modification time of the file is appended
as ``?v=...``: when the file changes, the URL changes and the browser downloads it.
"""

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static


register = template.Library()


@register.simple_tag
def asset(path):
    url = static(path)
    found = finders.find(path)
    if not found:
        return url
    return f"{url}?v={int(os.path.getmtime(found))}"
