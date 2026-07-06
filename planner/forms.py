from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Event, EventInvite, FriendRequest, Reminder


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
            self.fields["invited_friends"].queryset = accepted_friend_queryset(user)

        if self.instance.pk:
            self.fields["invited_friends"].initial = self.instance.invites.exclude(
                status=EventInvite.Status.DECLINED,
            ).values_list("invited_user_id", flat=True)

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "start_at",
            "end_at",
            "location",
            "visibility",
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
