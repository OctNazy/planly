from django.db import models
from django.contrib.auth.models import User


class Event(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        FRIENDS = "friends", "Friends"
        INVITE_ONLY = "invite_only", "Invite only"

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Reminder(models.Model):
    class Repeat(models.TextChoices):
        NONE = "none", "No repeat"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    class RemoveMode(models.TextChoices):
        KEEP_UNTIL_DONE = "keep_until_done", "Keep until done"
        HIDE_AFTER_TIME = "hide_after_time", "Hide after reminder time"

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    title = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    remind_date = models.DateField()
    remind_time = models.TimeField(null=True, blank=True)
    repeat = models.CharField(
        max_length=20,
        choices=Repeat.choices,
        default=Repeat.NONE,
    )
    remove_mode = models.CharField(
        max_length=30,
        choices=RemoveMode.choices,
        default=RemoveMode.KEEP_UNTIL_DONE,
    )
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
