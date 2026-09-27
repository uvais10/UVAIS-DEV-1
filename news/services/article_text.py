import re

import requests

USER_AGENT = USER_AGENT = "TripzidoBot/1.0"


def extract_article_text(url, max_characters=4000):
    """Fetch an article page and pull out its paragraph text."""
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException:
        return ""

    html = response.text
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.DOTALL | re.IGNORECASE)

    clean = []
    for paragraph in paragraphs:
        text = re.sub(r"<[^>]+>", " ", paragraph)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 40:
            clean.append(text)

    return "\n\n".join(clean)[:max_characters]
