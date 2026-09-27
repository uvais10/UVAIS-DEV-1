from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import CrawlRun, DiscoveredArticle
from news.services.content_generator import generate_content
from news.services.llm_client import LLMError


class Command(BaseCommand):
    help = "Generate original Tripzido content for classified-positive articles."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        run = CrawlRun.objects.create(stage=CrawlRun.Stage.GENERATE)
        articles = DiscoveredArticle.objects.filter(
            status=DiscoveredArticle.Status.CLASSIFIED, retry_count__lt=3
        )[: options["limit"]]

        found = processed = 0
        for article in articles:
            found += 1
            try:
                news = generate_content(article)
            except LLMError as exc:
                run.success = False
                run.error_detail = str(exc)
                self.stderr.write(self.style.ERROR(f"stopped - LLM not reachable: {exc}"))
                break
            processed += 1
            self.stdout.write(f"  wrote: {news.title[:60]}")

        run.found = found
        run.new = processed
        run.finished_at = timezone.now()
        run.save()
        self.stdout.write(f"generated {processed}/{found}")

