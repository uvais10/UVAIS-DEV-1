from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from news.models import DiscoveredArticle, TouristAttraction


def news_list(request, attraction_slug=None):
    attractions = TouristAttraction.objects.all()
    selected = None
    if attraction_slug:
        selected = get_object_or_404(TouristAttraction, slug=attraction_slug)
        articles = DiscoveredArticle.objects.filter(matched_attractions=selected)
    else:
        articles = DiscoveredArticle.objects.all().order_by("-published_at")

    paginator = Paginator(articles, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "news/news_list.html",
        {"articles": page_obj, "attractions": attractions, "selected": selected},
    )


def news_detail(request, slug):
    article = get_object_or_404(DiscoveredArticle, slug=slug)
    return render(request, "news/news_detail.html", {"article": article})
