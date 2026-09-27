from django.db import models


class TouristAttraction(models.Model):
    """One Kerala tourist attraction the crawler watches for."""

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True, default="")

    aliases = models.TextField(
        blank=True,
        help_text="Comma-separated alternative names, e.g. 'Alleppey, Alappuzha Backwaters'",
    )
    keywords = models.TextField(
        blank=True,
        help_text="Comma-separated extra match terms, e.g. 'backwaters, houseboat'",
    )
    district = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        
    def __str__(self) -> str:
        return self.name

    def all_match_terms(self) -> list[str]:
        """Name + aliases + keywords, lowercased - used by the crawler."""
        terms = [self.name, *self._split(self.aliases), *self._split(self.keywords)]
        return [t.lower().strip() for t in terms if t.strip()]

    @staticmethod
    def _split(value: str) -> list[str]:
        return value.split(",") if value else []



class NewsSource(models.Model):
    """One approved Kerala news website the crawler is allowed to monitor."""

    name = models.CharField(max_length=200, unique=True)
    base_url = models.URLField()
    rss_url = models.URLField(blank=True, help_text="Preferred discovery method")
    sitemap_url = models.URLField(blank=True, help_text="Used when there's no RSS feed")
    is_active = models.BooleanField(default=True)
    respect_robots_txt = models.BooleanField(default=True)
    crawl_interval_minutes = models.PositiveIntegerField(default=1440)
    last_crawled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
    
class DiscoveredArticle(models.Model):
    """Every article the crawler has ever seen from an approved source."""

    class Status(models.TextChoices):
        DISCOVERED = "discovered", "Discovered"
        CLASSIFIED = "classified", "Classified positive, awaiting content"
        CONTENT_GENERATED = "content_generated", "Content generated"
        PUBLISHED = "published", "Published"
        REJECTED_NEGATIVE = "rejected_negative", "Rejected - negative"
        REJECTED_NEUTRAL = "rejected_neutral", "Rejected - neutral/irrelevant"
        REJECTED_LOW_CONFIDENCE = "rejected_low_confidence", "Rejected - low confidence"
        FAILED = "failed", "Failed"


    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name="articles")
    url = models.URLField(max_length=1000, unique=True)
    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=300, unique=True, blank=True, default="")

    published_at = models.DateTimeField(null=True, blank=True)
    raw_content = models.TextField(blank=True)
    matched_attractions = models.ManyToManyField(TouristAttraction, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DISCOVERED)
    discovered_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)


    class Meta:
        ordering = ["-discovered_at"]

    def __str__(self) -> str:
        return self.title[:80]

    

class CrawlRun(models.Model):
    """One row per crawl run - the crawler's diary."""
    class Stage(models.TextChoices):
        CRAWL = "crawl", "Crawl"
        CLASSIFY = "classify", "Classify"
        GENERATE = "generate", "Generate"

    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name="crawl_runs", null=True, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.CRAWL)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=True)
    found = models.PositiveIntegerField(default=0)
    new = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
    error_detail = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        label = self.source.name if self.source else self.get_stage_display()
        return f"{label} - {self.started_at:%d %b %Y, %H:%M}"

class ArticleClassification(models.Model):
    """The LLM's verdict on one DiscoveredArticle."""

    class Verdict(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEGATIVE = "negative", "Negative"
        NEUTRAL = "neutral", "Neutral / irrelevant"

    article = models.OneToOneField(DiscoveredArticle, on_delete=models.CASCADE, related_name="classification")
    verdict = models.CharField(max_length=20, choices=Verdict.choices)
    confidence_score = models.FloatField(help_text="0.0 - 1.0")
    identified_attraction = models.ForeignKey(
        TouristAttraction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="classifications",
    )
    reason = models.TextField()
    raw_llm_response = models.JSONField(default=dict, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    classified_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"article {self.article_id} -> {self.verdict} ({self.confidence_score:.2f})"


class GeneratedNews(models.Model):
    """AI-written, original Tripzido article, ready for publishing."""

    article = models.OneToOneField(DiscoveredArticle, on_delete=models.CASCADE, related_name="generated_news")
    attraction = models.ForeignKey(
        TouristAttraction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="news_items",
    )
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True, blank=True)
    summary = models.TextField()
    content = models.TextField(help_text="Full article body, HTML paragraphs")
    image_url = models.URLField(blank=True)

    source_name = models.CharField(max_length=200, blank=True)
    source_url = models.URLField(blank=True)
    source_published_at = models.DateTimeField(null=True, blank=True)

    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title
