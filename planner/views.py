from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import EventForm, FriendRequestForm, ReminderForm
from .models import Event, FriendRequest, Reminder


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
def reminder_detail(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, owner=request.user)
    return render(request, "planner/reminder_detail.html", {"reminder": reminder})


@login_required
def reminder_update(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, owner=request.user)

    if request.method == "POST":
        form = ReminderForm(request.POST, instance=reminder)

        if form.is_valid():
            form.save()
            return redirect("reminder_detail", pk=reminder.pk)
    else:
        form = ReminderForm(instance=reminder)

    return render(
        request,
        "planner/reminder_form.html",
        {
            "form": form,
            "reminder": reminder,
        },
    )


@login_required
def reminder_delete(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, owner=request.user)

    if request.method == "POST":
        reminder.delete()
        return redirect("event_list")

    return render(
        request,
        "planner/reminder_confirm_delete.html",
        {"reminder": reminder},
    )


@login_required
def reminder_done(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, owner=request.user)

    if request.method == "POST":
        reminder.is_done = True
        reminder.save()

    return redirect("event_list")


@login_required
def friends(request):
    context = friends_context(request.user)
    return render(request, "planner/friends.html", context)


def friends_context(user, form=None):
    return {
        "form": form or FriendRequestForm(),
        "sent_friends": FriendRequest.objects.filter(
            from_user=user,
            status=FriendRequest.Status.ACCEPTED,
        ).select_related("to_user"),
        "received_friends": FriendRequest.objects.filter(
            to_user=user,
            status=FriendRequest.Status.ACCEPTED,
        ).select_related("from_user"),
        "incoming_requests": FriendRequest.objects.filter(
            to_user=user,
            status=FriendRequest.Status.PENDING,
        ).select_related("from_user"),
        "outgoing_requests": FriendRequest.objects.filter(
            from_user=user,
            status=FriendRequest.Status.PENDING,
        ).select_related("to_user"),
    }


@login_required
@require_POST
def friend_request_create(request):
    form = FriendRequestForm(request.POST)

    if form.is_valid():
        username = form.cleaned_data["username"]
        to_user = User.objects.filter(username=username).first()

        if to_user is None:
            form.add_error("username", "User not found.")
        elif to_user == request.user:
            form.add_error("username", "You cannot add yourself.")
        elif friend_request_exists(request.user, to_user):
            form.add_error("username", "Friend request already exists.")
        else:
            FriendRequest.objects.create(
                from_user=request.user,
                to_user=to_user,
            )
            return redirect("friends")

    context = friends_context(request.user, form)
    return render(request, "planner/friends.html", context)


def friend_request_exists(user, other_user):
    return FriendRequest.objects.filter(
        from_user=user,
        to_user=other_user,
    ).exists() or FriendRequest.objects.filter(
        from_user=other_user,
        to_user=user,
    ).exists()


@login_required
@require_POST
def friend_request_accept(request, pk):
    friend_request = get_object_or_404(
        FriendRequest,
        pk=pk,
        to_user=request.user,
        status=FriendRequest.Status.PENDING,
    )
    friend_request.status = FriendRequest.Status.ACCEPTED
    friend_request.save()
    return redirect("friends")


@login_required
@require_POST
def friend_request_reject(request, pk):
    friend_request = get_object_or_404(
        FriendRequest,
        pk=pk,
        to_user=request.user,
        status=FriendRequest.Status.PENDING,
    )
    friend_request.status = FriendRequest.Status.REJECTED
    friend_request.save()
    return redirect("friends")
