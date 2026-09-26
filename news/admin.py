from django.contrib import admin

from news.models import TouristAttraction,NewsSource,DiscoveredArticle,CrawlRun
@admin.register(TouristAttraction)
class TouristAttractionAdmin(admin.ModelAdmin):
    list_display = ("name", "district", "is_active")



@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "last_crawled_at")



@admin.register(DiscoveredArticle)
class DiscoveredArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "status", "discovered_at")
    list_filter = ("status",)


@admin.register(CrawlRun)
class CrawlRunAdmin(admin.ModelAdmin):
    list_display = ("source", "started_at", "finished_at", "success", "found", "new", "duplicates")
    list_filter = ("source", "success")


