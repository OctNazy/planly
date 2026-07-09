from django.contrib import admin
from .models import Event, EventInvite, FriendRequest, Notification, Reminder


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "start_at", "visibility")
    list_filter = ("visibility", "start_at")
    search_fields = ("title", "description", "location")


@admin.register(EventInvite)
class EventInviteAdmin(admin.ModelAdmin):
    list_display = ("event", "invited_user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("event__title", "invited_user__username")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "remind_date", "remind_time", "repeat", "is_done")
    list_filter = ("repeat", "remove_mode", "is_done", "remind_date")
    search_fields = ("title", "note")


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("from_user__username", "to_user__username")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "kind", "title", "is_read", "created_at")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("recipient__username", "actor__username", "title", "message")
