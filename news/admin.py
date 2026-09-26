from django.contrib import admin

from news.models import TouristAttraction,NewsSource,DiscoveredArticle
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
