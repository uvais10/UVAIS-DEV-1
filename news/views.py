from django.shortcuts import render,get_object_or_404

from news.models import DiscoveredArticle


def news_list(request):
    articles = DiscoveredArticle.objects.all()
    return render(request, "news/news_list.html", {"articles": articles})

def news_detail(request, slug):
    article = get_object_or_404(DiscoveredArticle, slug=slug)
    return render(request, "news/news_detail.html", {"article": article})
