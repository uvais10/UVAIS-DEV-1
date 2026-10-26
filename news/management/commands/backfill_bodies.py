"""
Backfill body text for Discovered articles that have none.

Self-contained on purpose: it includes its own HTML extractor, so it does NOT
depend on which version of crawl_news.py is installed.

Requires: beautifulsoup4   (pip install beautifulsoup4)

Usage:
    python manage.py backfill_bodies             # every article with no body
    python manage.py backfill_bodies --limit 5   # just the newest 5

Safe to re-run: articles that already have a body are never touched.
"""
import time

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db.models import Q

from news.models import DiscoveredArticle

USER_AGENT = "TripzidoBot/1.0"
FETCH_DELAY_SECONDS = 1      # politeness pause between page fetches
MIN_PARAGRAPH_CHARS = 40     # ignore captions/buttons when collecting text


def extract_article_content(url):
    """Best-effort body text: strip the page furniture, keep the paragraphs."""
    try:
        response = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"[extract] FETCH FAILED for {url}: {type(error).__name__}: {error}")
        return ""

    soup = BeautifulSoup(response.content, "html.parser")

    # Remove the furniture: scripts, styles, menus, headers, footers, sidebars
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # Prefer the real article container, fall back to the whole page
    container = soup.find("article") or soup.find(attrs={"role": "main"}) or soup

    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    return "\n\n".join(p for p in paragraphs if len(p) > MIN_PARAGRAPH_CHARS)


class Command(BaseCommand):
    help = "Fetch and save body text for discovered articles that have none."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of articles to backfill (default: all)",
        )

    def handle(self, *args, **options):
        qs = (
            DiscoveredArticle.objects.filter(
                Q(raw_content="") | Q(raw_content__isnull=True)
            )
            .order_by("-id")
        )

        limit = options.get("limit")
        articles = list(qs[:limit]) if limit else list(qs)

        if not articles:
            self.stdout.write(
                self.style.SUCCESS("Nothing to backfill - every article has a body.")
            )
            return

        self.stdout.write(f"Backfilling bodies for {len(articles)} article(s)...")
        filled, failed = 0, 0

        for article in articles:
            time.sleep(FETCH_DELAY_SECONDS)
            body = extract_article_content(article.url)

            if body:
                article.raw_content = body
                article.save(update_fields=["raw_content"])
                filled += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK   {len(body):>6} chars  {article.title[:60]}"
                    )
                )
            else:
                failed += 1
                self.stderr.write(f"  --   no body        {article.title[:60]}")

        self.stdout.write(self.style.SUCCESS(f"Done: filled={filled} failed={failed}"))
        if failed:
            self.stdout.write(
                "Articles with no body will be judged on their headline alone."
            )
