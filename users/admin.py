from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "name", "created_at")  # fields shown in the list view
    search_fields = ("email", "name")  # searchable fields
    list_filter = ("created_at",)  # filters on the right sidebar
