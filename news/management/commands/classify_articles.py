from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import CrawlRun, DiscoveredArticle
from news.services.classifier import classify_article
from news.services.llm_client import LLMError


class Command(BaseCommand):
    help = "Run LLM classification on discovered-but-unclassified articles."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        run = CrawlRun.objects.create(stage=CrawlRun.Stage.CLASSIFY)
        articles = DiscoveredArticle.objects.filter(
            status__in=[DiscoveredArticle.Status.DISCOVERED, DiscoveredArticle.Status.FAILED],
            retry_count__lt=3,
        )[: options["limit"]]

        found = processed = 0
        for article in articles:
            found += 1
            try:
                classification = classify_article(article)
            except LLMError as exc:
                run.success = False
                run.error_detail = str(exc)
                self.stderr.write(self.style.ERROR(f"stopped - LLM not reachable: {exc}"))
                break
            processed += 1
            self.stdout.write(f"  {classification.verdict:8s} {article.title[:60]}")

        run.found = found
        run.new = processed
        run.finished_at = timezone.now()
        run.save()
        self.stdout.write(f"classified {processed}/{found}")
