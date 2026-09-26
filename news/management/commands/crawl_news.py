import xml.etree.ElementTree as ET

import requests,re
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.db import IntegrityError

from news.models import DiscoveredArticle, NewsSource, TouristAttraction

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"
USER_AGENT = "TripzidoPracticeBot/1.0 (learning project)"


class Command(BaseCommand):
    help = "Fetch each source's news sitemap and save new relevant articles."

    def handle(self, *args, **options):
        for source in NewsSource.objects.filter(is_active=True):
            self.stdout.write(f"Crawling {source.name}...")
            self.crawl_source(source)

    def crawl_source(self, source):
        if not source.sitemap_url:
            self.stdout.write("  no sitemap url - skipping")
            return

        try:
            response = requests.get(
                source.sitemap_url,
                timeout=30,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
        except requests.RequestException as error:
            self.stderr.write(f"  fetch failed: {error}")
            return

        root = ET.fromstring(response.content)
        found, new, duplicates = 0, 0, 0

        for url in root.iter(f"{{{SITEMAP_NS}}}url"):
            loc = url.findtext(f"{{{SITEMAP_NS}}}loc")
            news = url.find(f"{{{NEWS_NS}}}news")
            if not loc or news is None:
                continue

            title = news.findtext(f"{{{NEWS_NS}}}title") or loc
            published = parse_datetime(
                news.findtext(f"{{{NEWS_NS}}}publication_date") or ""
            )

            matched = self.find_matches(title)
            if not matched:
                continue
            found += 1

            try:
                article, created = DiscoveredArticle.objects.get_or_create(
                    url=loc,
                    defaults={
                        "source": source,
                        "title": title[:500],
                        "slug": slugify(title)[:290] or slugify(loc)[:290],
                        "published_at": published,
                    },
                )
            except IntegrityError:
                self.stdout.write(f"  SKIP (slug clash): {title[:70]}")
                continue

            if not created:
                duplicates += 1
                continue

            article.matched_attractions.set(matched)
            new += 1
            self.stdout.write(f"  NEW: {title[:70]}")

        self.stdout.write(
            self.style.SUCCESS(f"  found={found} new={new} duplicates={duplicates}")
        )

    @staticmethod
    def find_matches(title):
        title_lower = title.lower()
        matched = []
        for attraction in TouristAttraction.objects.filter(is_active=True):
            for term in attraction.all_match_terms():
                if re.search(rf"\b{re.escape(term)}\b", title_lower):
                    matched.append(attraction)
                    break
        return matched

