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


class EventInvite(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    invited_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="event_invites",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "invited_user"],
                name="unique_event_invite",
            )
        ]

    def __str__(self):
        return f"{self.event} -> {self.invited_user}"


class EventChangeProposal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="change_proposals",
    )
    proposed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="event_change_proposals",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    proposed_invitees = models.ManyToManyField(
        User,
        blank=True,
        related_name="proposed_event_invites",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.event} changes by {self.proposed_by}"


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


class FriendRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_friend_requests",
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_friend_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                name="unique_friend_request",
            )
        ]

    def __str__(self):
        return f"{self.from_user} -> {self.to_user}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        FRIEND_REQUEST = "friend_request", "Friend request"
        FRIEND_ACCEPTED = "friend_accepted", "Friend accepted"
        EVENT_INVITE = "event_invite", "Event invite"
        EVENT_INVITE_ACCEPTED = "event_invite_accepted", "Event invite accepted"
        EVENT_INVITE_DECLINED = "event_invite_declined", "Event invite declined"
        EVENT_LEFT = "event_left", "Event left"
        EVENT_DELETED = "event_deleted", "Event deleted"
        CHANGE_PROPOSED = "change_proposed", "Change proposed"
        CHANGE_ACCEPTED = "change_accepted", "Change accepted"
        CHANGE_REJECTED = "change_rejected", "Change rejected"

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    friend_request = models.ForeignKey(
        FriendRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    change_proposal = models.ForeignKey(
        EventChangeProposal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return self.title
