from django import forms

from .models import Event, Reminder


class EventForm(forms.ModelForm):
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

    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "start_at",
            "end_at",
            "location",
            "visibility",
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
