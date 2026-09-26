from django.urls import path

from news import views

app_name = "news"

urlpatterns = [
    path("", views.news_list, name="news_list"),
    path("attraction/<slug:attraction_slug>/", views.news_list, name="news_by_attraction"),
    path("<slug:slug>/", views.news_detail, name="news_detail"),
]
