from django.conf import settings
from django.utils.text import slugify

from news.models import DiscoveredArticle, GeneratedNews
from news.services.llm_client import LLMError, call_local_llm_json

GENERATE_SYSTEM_PROMPT = """You write original tourism news for Tripzido, a Kerala travel website.
Rewrite the source article in your own words - never copy sentences verbatim.
Keep facts accurate; do not invent details not in the source. Friendly, useful tone for travellers.

Do not invent facilities, amenities, prices, dates, organizations,
quotes, or logistics that are not stated in the source article.
If a detail is unknown, write generally instead of specifically.
Never claim popularity, outcomes, or events that could not yet be true.


Respond with ONLY a JSON object, no other text:
{
  "title": "<display title>",
  "summary": "<2-3 sentence summary>",
  "content": "<full article, 300-600 words, as HTML paragraphs like <p>...</p><p>...</p>"
}
"""


def generate_content(article):
    attraction = article.classification.identified_attraction
    prompt = (
        f"Attraction: {attraction.name if attraction else 'unspecified'}\n\n"
        f"Source title: {article.title}\n\n"
        f"Source article:\n{article.raw_content[:6000]}"
    )

    try:
        result = call_local_llm_json(prompt, system=GENERATE_SYSTEM_PROMPT)
    except LLMError as exc:
        article.status = DiscoveredArticle.Status.FAILED
        article.failure_reason = str(exc)
        article.retry_count += 1
        article.save(update_fields=["status", "failure_reason", "retry_count"])
        raise

    title = (result.get("title") or article.title)[:300]
    slug = slugify(title)[:280] or "article"
    if GeneratedNews.objects.filter(slug=slug).exists():
        slug = f"{slug}-{article.id}"

    news = GeneratedNews.objects.create(
        article=article,
        attraction=attraction,
        title=title,
        slug=slug,
        summary=result.get("summary", ""),
        content=result.get("content", ""),
        source_name=article.source.name,
        source_url=article.url,
        source_published_at=article.published_at,
    )

    article.status = DiscoveredArticle.Status.CONTENT_GENERATED
    article.save(update_fields=["status"])

    if getattr(settings, "NEWS_AUTO_PUBLISH", False):
        news.is_published = True
        news.save(update_fields=["is_published"])
        article.status = DiscoveredArticle.Status.PUBLISHED
        article.save(update_fields=["status"])

    return news
