from django.contrib import admin

from news.models import TouristAttraction,NewsSource,DiscoveredArticle,CrawlRun,ArticleClassification,GeneratedNews
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

@admin.register(ArticleClassification)
class ArticleClassificationAdmin(admin.ModelAdmin):
    list_display = ("article", "verdict", "confidence_score", "identified_attraction", "classified_at")
    list_filter = ("verdict",)


@admin.register(GeneratedNews)
class GeneratedNewsAdmin(admin.ModelAdmin):
    list_display = ("title", "attraction", "is_published", "created_at")
    list_filter = ("is_published",)
    prepopulated_fields = {"slug": ("title",)}


