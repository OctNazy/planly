import calendar as calendar_module
from datetime import date, datetime, time

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import ProfileForm
from accounts.models import Profile
from .forms import EventForm, FriendRequestForm, ReminderForm, accepted_friend_queryset
from .models import Event, EventInvite, FriendRequest, Reminder


def home_header(user):
    current_hour = timezone.localtime().hour

    if 5 <= current_hour < 12:
        icon = "☀️"
        greetings = [
            "Good morning",
            "Morning",
            "Start the day",
        ]
    elif 12 <= current_hour < 18:
        icon = "🌤️"
        greetings = [
            "Good afternoon",
            "Hey",
            "Hope your day is going well",
        ]
    elif 18 <= current_hour < 23:
        icon = "🌙"
        greetings = [
            "Good evening",
            "Evening",
            "Time to check the plans",
        ]
    else:
        icon = "✨"
        greetings = [
            "Still planning",
            "Late night plans",
            "Quiet night",
        ]

    day_number = timezone.localdate().toordinal()
    greeting = greetings[(day_number + user.id) % len(greetings)]
    return {
        "greeting": f"{greeting}, {user.username}!",
        "greeting_icon": icon,
        "today": timezone.localdate().strftime("%B %-d, %A"),
    }


def active_event_invites():
    return EventInvite.objects.exclude(
        status=EventInvite.Status.DECLINED,
    ).select_related(
        "invited_user",
        "invited_user__profile",
    ).order_by("invited_user__username")


def visible_events_for(user):
    return Event.objects.filter(
        Q(owner=user)
        | Q(
            invites__invited_user=user,
            invites__status=EventInvite.Status.ACCEPTED,
        )
    ).distinct().select_related(
        "owner",
        "owner__profile",
    ).prefetch_related(
        Prefetch("invites", queryset=active_event_invites(), to_attr="active_invites")
    ).order_by("start_at")


def event_cards(events):
    cards = []

    for event in events:
        active_invites = list(getattr(event, "active_invites", []))
        participants = [event.owner]
        participants.extend(invite.invited_user for invite in active_invites)

        cards.append(
            {
                "event": event,
                "is_group": bool(active_invites),
                "participants": participants,
            }
        )

    return cards


def event_cards_by_date(events):
    cards_by_date = {}

    for card in event_cards(events):
        event_date = timezone.localtime(card["event"].start_at).date()
        cards_by_date.setdefault(event_date, []).append(card)

    return cards_by_date


def reminders_by_date(reminders):
    items_by_date = {}

    for reminder in reminders:
        items_by_date.setdefault(reminder.remind_date, []).append(reminder)

    return items_by_date


def calendar_dots(item_count):
    if item_count == 0:
        return range(0)
    if item_count == 1:
        return range(1)
    if item_count <= 3:
        return range(2)
    return range(3)


def selected_friend_ids(form):
    values = form["invited_friends"].value() or []
    return [int(value) for value in values]


def event_form_context(form, event=None):
    return {
        "form": form,
        "event": event,
        "friend_choices": form.fields["invited_friends"].queryset,
        "selected_friend_ids": selected_friend_ids(form),
        "is_group_checked": bool(form["is_group"].value()),
    }


def add_months(month_date, offset):
    month_index = month_date.month - 1 + offset
    year = month_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def calendar_month_data(month_date, cards_by_date, reminders_by_date, today):
    weeks = []

    for week in calendar_module.Calendar().monthdatescalendar(
        month_date.year,
        month_date.month,
    ):
        days = []

        for day in week:
            cards = cards_by_date.get(day, [])
            reminders = reminders_by_date.get(day, [])
            days.append(
                {
                    "date": day,
                    "number": day.day,
                    "in_month": day.month == month_date.month,
                    "is_today": day == today,
                    "date_key": day.isoformat(),
                    "cards": cards,
                    "reminders": reminders,
                    "event_dots": calendar_dots(len(cards)),
                    "reminder_dots": calendar_dots(len(reminders)),
                    "has_plans": bool(cards or reminders),
                }
            )

        weeks.append(days)

    return {
        "short_title": month_date.strftime("%b"),
        "year": month_date.year,
        "label_column": month_date.weekday() + 1,
        "is_current": month_date.year == today.year and month_date.month == today.month,
        "weeks": weeks,
    }


@login_required
def event_list(request):
    profile, _created = Profile.objects.get_or_create(user=request.user)
    home = home_header(request.user)
    events = visible_events_for(request.user)
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
            "greeting": home["greeting"],
            "greeting_icon": home["greeting_icon"],
            "today": home["today"],
            "profile": profile,
            "event_cards": event_cards(events),
            "reminders": reminders,
        },
    )


@login_required
def calendar(request):
    today = timezone.localdate()
    current_month = date(today.year, today.month, 1)
    first_month = add_months(current_month, -12)
    last_month_end = add_months(current_month, 13)
    timezone_info = timezone.get_current_timezone()
    period_start = timezone.make_aware(
        datetime.combine(first_month, time.min),
        timezone_info,
    )
    period_end = timezone.make_aware(
        datetime.combine(last_month_end, time.min),
        timezone_info,
    )
    events = visible_events_for(request.user).filter(
        start_at__gte=period_start,
        start_at__lt=period_end,
    )
    reminders = Reminder.objects.filter(
        owner=request.user,
        is_done=False,
        remind_date__gte=first_month,
        remind_date__lt=last_month_end,
    ).exclude(
        remove_mode=Reminder.RemoveMode.HIDE_AFTER_TIME,
        remind_date__lt=today,
    ).exclude(
        remove_mode=Reminder.RemoveMode.HIDE_AFTER_TIME,
        remind_date=today,
        remind_time__lt=timezone.localtime().time(),
    ).order_by("remind_date", "remind_time")
    cards_by_date = event_cards_by_date(events)
    reminder_items_by_date = reminders_by_date(reminders)
    calendar_months = [
        calendar_month_data(
            add_months(current_month, offset),
            cards_by_date,
            reminder_items_by_date,
            today,
        )
        for offset in range(-12, 13)
    ]

    return render(
        request,
        "planner/calendar.html",
        {
            "calendar_months": calendar_months,
            "calendar_year": today.year,
            "weekdays": ["M", "T", "W", "T", "F", "S", "S"],
        },
    )


@login_required
def notifications(request):
    event_invites = EventInvite.objects.filter(
        invited_user=request.user,
        status=EventInvite.Status.PENDING,
    ).select_related(
        "event",
        "event__owner",
        "event__owner__profile",
    ).order_by("event__start_at")
    friend_requests = FriendRequest.objects.filter(
        to_user=request.user,
        status=FriendRequest.Status.PENDING,
    ).select_related("from_user", "from_user__profile")
    return render(
        request,
        "planner/notifications.html",
        {
            "event_invites": event_invites,
            "friend_requests": friend_requests,
        },
    )


@login_required
def event_detail(request, pk):
    event = get_object_or_404(
        Event.objects.select_related("owner").filter(
            Q(owner=request.user)
            | Q(
                invites__invited_user=request.user,
                invites__status=EventInvite.Status.ACCEPTED,
            )
        ),
        pk=pk,
    )
    event_invites = event.invites.select_related(
        "invited_user",
        "invited_user__profile",
    ).order_by(
        "invited_user__username",
    )
    participants = [event.owner]
    participants.extend(
        invite.invited_user
        for invite in event_invites
        if invite.status != EventInvite.Status.DECLINED
    )
    return render(
        request,
        "planner/event_detail.html",
        {
            "event": event,
            "event_invites": event_invites,
            "is_owner": event.owner_id == request.user.id,
            "participants": participants,
        },
    )


@login_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST, user=request.user)

        if form.is_valid():
            event = form.save(commit=False)
            event.owner = request.user
            event.visibility = event_visibility(form)
            event.save()
            sync_event_invites(event, form.cleaned_data["invited_friends"], form)
            return redirect("event_detail", pk=event.pk)
    else:
        form = EventForm(user=request.user)

    return render(request, "planner/event_form.html", event_form_context(form))


@login_required
def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    if request.method == "POST":
        form = EventForm(request.POST, instance=event, user=request.user)

        if form.is_valid():
            event = form.save(commit=False)
            event.visibility = event_visibility(form)
            event.save()
            sync_event_invites(event, form.cleaned_data["invited_friends"], form)
            return redirect("event_detail", pk=event.pk)
    else:
        form = EventForm(instance=event, user=request.user)

    return render(
        request,
        "planner/event_form.html",
        event_form_context(form, event),
    )


@login_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, owner=request.user)

    if request.method == "POST":
        event.delete()
        return redirect("event_list")

    return render(request, "planner/event_confirm_delete.html", {"event": event})


def event_visibility(form):
    if form.cleaned_data["is_group"]:
        return Event.Visibility.INVITE_ONLY
    return Event.Visibility.PRIVATE


def sync_event_invites(event, invited_friends, form):
    if not form.cleaned_data["is_group"]:
        invited_friends = []

    selected_ids = {friend.id for friend in invited_friends}

    EventInvite.objects.filter(event=event).exclude(
        invited_user_id__in=selected_ids,
    ).delete()

    for friend in invited_friends:
        invite, created = EventInvite.objects.get_or_create(
            event=event,
            invited_user=friend,
        )

        if not created and invite.status == EventInvite.Status.DECLINED:
            invite.status = EventInvite.Status.PENDING
            invite.save()


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


@login_required
def settings(request):
    profile, _created = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)

        if form.is_valid():
            form.save()
            return redirect("settings")
    else:
        form = ProfileForm(instance=profile)

    return render(
        request,
        "planner/settings.html",
        {
            "form": form,
            "profile": profile,
        },
    )


def friends_context(user, form=None):
    return {
        "form": form or FriendRequestForm(),
        "friends": accepted_friend_queryset(user).select_related("profile"),
        "event_invites": EventInvite.objects.filter(
            invited_user=user,
            status=EventInvite.Status.PENDING,
        ).select_related(
            "event",
            "event__owner",
            "event__owner__profile",
        ).order_by("event__start_at"),
        "sent_friends": FriendRequest.objects.filter(
            from_user=user,
            status=FriendRequest.Status.ACCEPTED,
        ).select_related("to_user", "to_user__profile"),
        "received_friends": FriendRequest.objects.filter(
            to_user=user,
            status=FriendRequest.Status.ACCEPTED,
        ).select_related("from_user", "from_user__profile"),
        "incoming_requests": FriendRequest.objects.filter(
            to_user=user,
            status=FriendRequest.Status.PENDING,
        ).select_related("from_user", "from_user__profile"),
        "outgoing_requests": FriendRequest.objects.filter(
            from_user=user,
            status=FriendRequest.Status.PENDING,
        ).select_related("to_user", "to_user__profile"),
    }


@login_required
def friend_request_create(request):
    if request.method == "POST":
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
    else:
        form = FriendRequestForm()

    return render(request, "planner/friend_form.html", {"form": form})


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


@login_required
@require_POST
def event_invite_accept(request, pk):
    invite = get_object_or_404(
        EventInvite,
        pk=pk,
        invited_user=request.user,
        status=EventInvite.Status.PENDING,
    )
    invite.status = EventInvite.Status.ACCEPTED
    invite.save()
    return redirect("event_detail", pk=invite.event.pk)


@login_required
@require_POST
def event_invite_decline(request, pk):
    invite = get_object_or_404(
        EventInvite,
        pk=pk,
        invited_user=request.user,
        status=EventInvite.Status.PENDING,
    )
    invite.status = EventInvite.Status.DECLINED
    invite.save()
    return redirect("event_list")
