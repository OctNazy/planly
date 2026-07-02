from django.contrib import admin
from .models import Event, Reminder


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "start_at", "visibility")
    list_filter = ("visibility", "start_at")
    search_fields = ("title", "description", "location")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "remind_date", "remind_time", "repeat", "is_done")
    list_filter = ("repeat", "remove_mode", "is_done", "remind_date")
    search_fields = ("title", "note")
