"""
Fetch each source's news sitemap and save new relevant articles.

Stage 1 of the Tripzido news pipeline: find the news.

CHANGES IN THIS VERSION (vs the previous file):
  1. robots_allows() normalises base_url (adds https:// if missing), so a
     scheme-less base_url can no longer turn into the relative path
     "/robots.txt" and silently fail.
  2. robots_allows() is now an instance method and PRINTS the real reason on
     every failure path. A silent `return False` is indistinguishable from a
     genuine "disallowed" - that ambiguity cost us a debugging session.
  3. The skip message now points at the reason printed above it.

Everything else (sitemap parsing, matching, saving, CrawlRun bookkeeping) is
unchanged from the previous version.
"""
import re, requests, time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib import robotparser
from urllib.parse import urljoin
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from news.models import CrawlRun, DiscoveredArticle, NewsSource, TouristAttraction

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"
USER_AGENT = "TripzidoBot/1.0"
FETCH_DELAY_SECONDS = 1
MIN_PARAGRAPH_CHARS = 40


def extract_article_content(url):
    """Best-effort body text: strip the page furniture, keep the paragraphs."""
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"[extract] FETCH FAILED for {url}: {type(error).__name__}: {error}")
        return ""

    soup = BeautifulSoup(response.content, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    container = soup.find("article") or soup.find(attrs={"role": "main"}) or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]

    if not paragraphs:
        print(f"[extract] NO PARAGRAPHS in container '{container.name}' for {url}")
        return ""

    kept = [p for p in paragraphs if len(p) > MIN_PARAGRAPH_CHARS]
    print(f"[extract] {len(paragraphs)} paragraphs found, {len(kept)} kept, longest {max(len(p) for p in paragraphs)} chars")
    return "\n\n".join(kept)




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
            self.stdout.write("  robots.txt check failed - skipping (reason above)")
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

            time.sleep(FETCH_DELAY_SECONDS)
            body = extract_article_content(loc)
            if body:
                article.raw_content = body
                article.save(update_fields=["raw_content"])
                self.stdout.write(f"  NEW: {title[:70]} ({len(body)} chars)")
            else:
                self.stdout.write(f"  NEW: {title[:70]} (body fetch FAILED - headline only)")


        self.stdout.write(
            self.style.SUCCESS(f"  found={found} new={new} duplicates={duplicates}")
        )
        return found, new, duplicates

    def robots_allows(self, source):
        """Check the source's robots.txt using our own User-Agent.

        Never denies silently: every failure path prints WHY, because a silent
        `return False` here is indistinguishable from a genuine refusal.
        """
        if not source.respect_robots_txt:
            return True

        base_url = (source.base_url or "").strip()
        if not base_url:
            self.stderr.write("  robots: source.base_url is empty - cannot check robots.txt")
            return False
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url

        robots_url = urljoin(base_url, "/robots.txt")
        try:
            response = requests.get(
                robots_url,
                timeout=30,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
        except requests.RequestException as error:
            self.stderr.write(
                f"  robots: could not read {robots_url} ({type(error).__name__}: {error}) "
                "- failing closed"
            )
            return False

        parser = robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())

        target = source.sitemap_url or base_url
        allowed = parser.can_fetch(USER_AGENT, target)
        if not allowed:
            self.stderr.write(f"  robots: {robots_url} disallows {target}")
        return allowed

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
