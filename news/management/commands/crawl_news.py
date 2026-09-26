import re
import xml.etree.ElementTree as ET
from urllib import robotparser
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from news.models import CrawlRun, DiscoveredArticle, NewsSource, TouristAttraction

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"
USER_AGENT = "TripzidoPracticeBot/1.0 (learning project)"


class Command(BaseCommand):
    help = "Fetch each source's news sitemap and save new relevant articles."

    def handle(self, *args, **options):
        for source in NewsSource.objects.filter(is_active=True):
            self.stdout.write(f"Crawling {source.name}...")
            run = CrawlRun.objects.create(source=source)
            try:
                run.found, run.new, run.duplicates = self.crawl_source(source)
            except Exception as error:
                run.success = False
                run.error_detail = str(error)
                self.stderr.write(f"  FAILED: {error}")
            run.finished_at = timezone.now()
            run.save()
            source.last_crawled_at = run.started_at
            source.save()

    def crawl_source(self, source):
        if not source.sitemap_url:
            return 0, 0, 0

        if not self.robots_allows(source):
            self.stdout.write("  robots.txt says not allowed - skipping")
            return 0, 0, 0

        try:
            response = requests.get(
                source.sitemap_url,
                timeout=30,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
        except requests.RequestException as error:
            self.stderr.write(f"  fetch failed: {error}")
            raise

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
        return found, new, duplicates
    @staticmethod
    def robots_allows(source):
        if not source.respect_robots_txt:
            return True
        try:
            response = requests.get(
                urljoin(source.base_url, "/robots.txt"),
                timeout=30,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
        except requests.RequestException:
            return False
        parser = robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser.can_fetch(USER_AGENT, source.sitemap_url)

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
