from django.db import models


class TouristAttraction(models.Model):
    """One Kerala tourist attraction the crawler watches for."""

    name = models.CharField(max_length=200, unique=True)
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

    class Meta:
        ordering = ["-discovered_at"]

    def __str__(self) -> str:
        return self.title[:80]
