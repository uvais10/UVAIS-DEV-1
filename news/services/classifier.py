from django.conf import settings
from django.utils import timezone

from news.models import ArticleClassification, DiscoveredArticle, TouristAttraction
from news.services.article_text import extract_article_text
from news.services.llm_client import LLMError, call_local_llm_json

CLASSIFY_SYSTEM_PROMPT = """You are a strict news classifier for a Kerala tourism website.
Classify the article as exactly one of: positive, negative, neutral.

positive: positive tourism development - new facilities, increased tourist arrivals,
awards, improved infrastructure, new attractions or activities.
negative: accidents, closures, damage, restrictions, security issues, disasters, or any
other development that would make a tourist think twice about visiting.
neutral: does not contain meaningful positive tourism information (politics, unrelated
local news, routine announcements, etc).

Respond with ONLY a JSON object, no other text:
{"verdict": "positive|negative|neutral", "confidence": 0.0-1.0,
 "attraction": "<matched attraction name from the provided list, or null>",
 "reason": "<one sentence explaining the verdict>"}
"""


def classify_article(article):
    attractions = list(article.matched_attractions.all()) or list(
        TouristAttraction.objects.filter(is_active=True)
    )
    names = ", ".join(a.name for a in attractions)

    text = article.raw_content or extract_article_text(article.url)
    if not article.raw_content and text:
        article.raw_content = text
        article.save(update_fields=["raw_content"])

    prompt = (
        f"Known attractions: {names}\n\n"
        f"Title: {article.title}\n\n"
        f"Article:\n{text[:3000]}"
    )

    try:
        result = call_local_llm_json(prompt, system=CLASSIFY_SYSTEM_PROMPT)
    except LLMError as exc:
        article.status = DiscoveredArticle.Status.FAILED
        article.failure_reason = str(exc)
        article.retry_count += 1
        article.save(update_fields=["status", "failure_reason", "retry_count"])
        raise

    verdict = result.get("verdict", "neutral")
    if verdict not in ArticleClassification.Verdict.values:
        verdict = ArticleClassification.Verdict.NEUTRAL

    attraction_obj = None
    attraction_name = result.get("attraction")
    if attraction_name:
        attraction_obj = TouristAttraction.objects.filter(name__iexact=attraction_name).first()

    classification = ArticleClassification.objects.create(
        article=article,
        verdict=verdict,
        confidence_score=float(result.get("confidence") or 0.0),
        identified_attraction=attraction_obj,
        reason=result.get("reason", ""),
        raw_llm_response=result,
        model_name=getattr(settings, "LOCAL_LLM_MODEL", ""),
    )

    threshold = getattr(settings, "NEWS_AI_CONFIDENCE_THRESHOLD", 0.75)
    if verdict == ArticleClassification.Verdict.POSITIVE and classification.confidence_score >= threshold:
        article.status = DiscoveredArticle.Status.CLASSIFIED
    elif verdict == ArticleClassification.Verdict.NEGATIVE:
        article.status = DiscoveredArticle.Status.REJECTED_NEGATIVE
    elif verdict == ArticleClassification.Verdict.POSITIVE:
        article.status = DiscoveredArticle.Status.REJECTED_LOW_CONFIDENCE
    else:
        article.status = DiscoveredArticle.Status.REJECTED_NEUTRAL

    article.processed_at = timezone.now()
    article.save(update_fields=["status", "processed_at"])
    return classification
