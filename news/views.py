from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from news.models import GeneratedNews, TouristAttraction


def news_list(request, attraction_slug=None):
    attractions = TouristAttraction.objects.all()
    selected = None
    articles = GeneratedNews.objects.filter(is_published=True)
    if attraction_slug:
        selected = get_object_or_404(TouristAttraction, slug=attraction_slug)
        articles = articles.filter(attraction=selected)
    articles = articles.order_by("-created_at")

    paginator = Paginator(articles, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "news/news_list.html",
        {"articles": page_obj, "attractions": attractions, "selected": selected},
    )


def news_detail(request, slug):
    article = get_object_or_404(GeneratedNews, slug=slug, is_published=True)
    return render(request, "news/news_detail.html", {"article": article})
