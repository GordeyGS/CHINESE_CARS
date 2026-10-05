from django.contrib import admin

from .models import RecommendationCondition, RecommendationRule


class RecommendationConditionInline(admin.TabularInline):
    model = RecommendationCondition
    extra = 0


@admin.register(RecommendationRule)
class RecommendationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "rule_kind", "weight", "priority", "is_active")
    search_fields = ("name", "code", "description")
    list_filter = ("rule_kind", "is_active")
    inlines = (RecommendationConditionInline,)


admin.site.register(RecommendationCondition)
