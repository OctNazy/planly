from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from .models import (
    Event,
    EventChangeProposal,
    EventInvite,
    FriendRequest,
    Reminder,
)


def accepted_friend_queryset(user):
    return User.objects.filter(
        Q(
            received_friend_requests__from_user=user,
            received_friend_requests__status=FriendRequest.Status.ACCEPTED,
        )
        | Q(
            sent_friend_requests__to_user=user,
            sent_friend_requests__status=FriendRequest.Status.ACCEPTED,
        )
    ).distinct().order_by("username")


class EventForm(forms.ModelForm):
    visibility = forms.ChoiceField(
        label="Who can see this event?",
        choices=[
            (Event.Visibility.PRIVATE, "Only me"),
            (Event.Visibility.FRIENDS, "My friends"),
        ],
    )
    is_group = forms.BooleanField(
        label="Group event",
        required=False,
        help_text="Turn this on to invite friends.",
    )
    invited_friends = forms.ModelMultipleChoiceField(
        label="Invite friends",
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Only accepted friends appear here.",
    )
    start_at = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    end_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["invited_friends"].queryset = accepted_friend_queryset(
                user
            ).select_related("profile")

        if self.instance.pk:
            active_invites = self.instance.invites.exclude(
                status=EventInvite.Status.DECLINED,
            )
            self.fields["is_group"].initial = active_invites.exists()
            self.fields["invited_friends"].initial = active_invites.values_list(
                "invited_user_id",
                flat=True,
            )

            if self.instance.visibility == Event.Visibility.INVITE_ONLY:
                self.fields["visibility"].initial = Event.Visibility.PRIVATE

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if start_at and end_at and end_at <= start_at:
            self.add_error("end_at", "End time must be after start time.")

        return cleaned_data

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "start_at",
            "end_at",
            "location",
            "visibility",
            "is_group",
            "invited_friends",
        ]


class EventChangeProposalForm(forms.ModelForm):
    invited_friends = forms.ModelMultipleChoiceField(
        label="Invite more friends",
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    start_at = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    end_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    def __init__(self, *args, user, event, **kwargs):
        super().__init__(*args, **kwargs)
        current_participant_ids = event.invites.exclude(
            status=EventInvite.Status.DECLINED,
        ).values_list("invited_user_id", flat=True)
        self.fields["invited_friends"].queryset = accepted_friend_queryset(
            user
        ).exclude(
            id__in=[event.owner_id, user.id, *current_participant_ids],
        ).select_related("profile")

        if self.instance.pk:
            self.fields["invited_friends"].initial = (
                self.instance.proposed_invitees.all()
            )

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if start_at and end_at and end_at <= start_at:
            self.add_error("end_at", "End time must be after start time.")

        return cleaned_data

    class Meta:
        model = EventChangeProposal
        fields = [
            "title",
            "description",
            "start_at",
            "end_at",
            "location",
            "invited_friends",
        ]


class ReminderForm(forms.ModelForm):
    remind_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    remind_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )

    class Meta:
        model = Reminder
        fields = [
            "title",
            "note",
            "remind_date",
            "remind_time",
            "repeat",
            "remove_mode",
        ]


class FriendRequestForm(forms.Form):
    username = forms.CharField(
        label="Friend username",
        max_length=150,
    )
