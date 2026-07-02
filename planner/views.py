from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import EventForm, ReminderForm
from .models import Event, Reminder


@login_required
def event_list(request):
    events = Event.objects.filter(owner=request.user).order_by("start_at")
    reminders = Reminder.objects.filter(
        owner=request.user,
        is_done=False,
    )
    today = timezone.localdate()
    current_time = timezone.localtime().time()
    reminders = reminders.exclude(
        remove_mode=Reminder.RemoveMode.HIDE_AFTER_TIME,
        remind_date__lt=today,
    ).exclude(
        remove_mode=Reminder.RemoveMode.HIDE_AFTER_TIME,
        remind_date=today,
        remind_time__lt=current_time,
    ).order_by("remind_date", "remind_time")
    return render(
        request,
        "planner/event_list.html",
        {
            "events": events,
            "reminders": reminders,
        },
    )


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)
    return render(request, "planner/event_detail.html", {"event": event})


@login_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST)

        if form.is_valid():
            event = form.save(commit=False)
            event.owner = request.user
            event.save()
            return redirect("event_detail", pk=event.pk)
    else:
        form = EventForm()

    return render(request, "planner/event_form.html", {"form": form})


@login_required
def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    if request.method == "POST":
        form = EventForm(request.POST, instance=event)

        if form.is_valid():
            form.save()
            return redirect("event_detail", pk=event.pk)
    else:
        form = EventForm(instance=event)

    return render(
        request,
        "planner/event_form.html",
        {
            "form": form,
            "event": event,
        },
    )


@login_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    if request.method == "POST":
        event.delete()
        return redirect("event_list")

    return render(request, "planner/event_confirm_delete.html", {"event": event})


@login_required
def reminder_create(request):
    if request.method == "POST":
        form = ReminderForm(request.POST)

        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.owner = request.user
            reminder.save()
            return redirect("event_list")
    else:
        form = ReminderForm()

    return render(
        request,
        "planner/reminder_form.html",
        {
            "form": form,
        },
    )


@login_required
def reminder_done(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, owner=request.user)

    if request.method == "POST":
        reminder.is_done = True
        reminder.save()

    return redirect("event_list")


@login_required
def reminder_detail(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, owner=request.user)
    return render(request, "planner/reminder_detail.html", {"reminder": reminder})
