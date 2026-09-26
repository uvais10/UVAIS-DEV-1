from django.shortcuts import get_object_or_404, render

from news.models import DiscoveredArticle, TouristAttraction


def news_list(request, attraction_slug=None):
    attractions = TouristAttraction.objects.all()
    selected = None
    if attraction_slug:
        selected = get_object_or_404(TouristAttraction, slug=attraction_slug)
        articles = DiscoveredArticle.objects.filter(matched_attractions=selected)
    else:
        articles = DiscoveredArticle.objects.all()
    return render(
        request,
        "news/news_list.html",
        {"articles": articles, "attractions": attractions, "selected": selected},
    )


def news_detail(request, slug):
    article = get_object_or_404(DiscoveredArticle, slug=slug)
    return render(request, "news/news_detail.html", {"article": article})
