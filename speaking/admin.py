from django.contrib import admin
from .models import SpeakingSession

@admin.register(SpeakingSession)
class SpeakingSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "created_at")
    search_fields = ("user__email", "question", "user_text", "ai_text")
    list_filter = ("created_at",)
