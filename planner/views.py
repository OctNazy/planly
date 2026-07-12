import calendar as calendar_module
from datetime import date, datetime, time

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import ProfileForm
from accounts.models import Profile
from .forms import (
    EventChangeProposalForm,
    EventForm,
    FriendRequestForm,
    ReminderForm,
    accepted_friend_queryset,
)
from .models import (
    Event,
    EventChangeProposal,
    EventInvite,
    FriendRequest,
    Notification,
    Reminder,
)


def notify_user(
    recipient,
    kind,
    title,
    message="",
    actor=None,
    event=None,
    friend_request=None,
    change_proposal=None,
):
    if actor and actor.id == recipient.id:
        return None

    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        kind=kind,
        title=title,
        message=message,
        event=event,
        friend_request=friend_request,
        change_proposal=change_proposal,
    )


def clear_action_notifications(
    recipient,
    kind,
    event=None,
    friend_request=None,
    change_proposal=None,
):
    notifications = Notification.objects.filter(
        recipient=recipient,
        kind=kind,
    )

    if event is not None:
        notifications = notifications.filter(event=event)
    if friend_request is not None:
        notifications = notifications.filter(friend_request=friend_request)
    if change_proposal is not None:
        notifications = notifications.filter(change_proposal=change_proposal)

    notifications.delete()


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


def participating_events(user):
    return Event.objects.filter(
        Q(owner=user)
        | Q(
            invites__invited_user=user,
            invites__status=EventInvite.Status.ACCEPTED,
        )
    ).distinct()


def shared_events_between(user, other_user):
    user_event_ids = participating_events(user).values("pk")
    return participating_events(other_user).filter(
        pk__in=user_event_ids,
    ).distinct()


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


def change_proposal_cards(event, participants):
    proposals = event.change_proposals.filter(
        status=EventChangeProposal.Status.PENDING,
    ).select_related(
        "proposed_by",
        "proposed_by__profile",
    ).prefetch_related(
        "proposed_invitees",
        "proposed_invitees__profile",
    )
    participant_ids = {person.id for person in participants}
    cards = []

    for proposal in proposals:
        new_invitees = list(proposal.proposed_invitees.all())
        proposed_participants = list(participants)
        proposed_participants.extend(
            person for person in new_invitees if person.id not in participant_ids
        )
        cards.append(
            {
                "proposal": proposal,
                "participants": proposed_participants,
                "title_changed": proposal.title != event.title,
                "description_changed": proposal.description != event.description,
                "start_changed": proposal.start_at != event.start_at,
                "end_changed": proposal.end_at != event.end_at,
                "location_changed": proposal.location != event.location,
                "invitees_changed": bool(new_invitees),
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


def calendar_period(today):
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
    return current_month, first_month, last_month_end, period_start, period_end


def calendar_months_for(events, reminders, today, current_month):
    cards_by_date = event_cards_by_date(events)
    reminder_items_by_date = reminders_by_date(reminders)
    return [
        calendar_month_data(
            add_months(current_month, offset),
            cards_by_date,
            reminder_items_by_date,
            today,
        )
        for offset in range(-12, 13)
    ]


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
def home(request):
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
        "planner/home.html",
        {
            "events": events,
            "greeting": home["greeting"],
            "greeting_icon": home["greeting_icon"],
            "today": home["today"],
            "profile": profile,
            "event_cards": event_cards(events),
            "reminders": reminders,
            "unread_notification_count": Notification.objects.filter(
                recipient=request.user,
                is_read=False,
            ).count(),
        },
    )


@login_required
def calendar(request):
    today = timezone.localdate()
    (
        current_month,
        first_month,
        last_month_end,
        period_start,
        period_end,
    ) = calendar_period(today)
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

    return render(
        request,
        "planner/calendar.html",
        {
            "calendar_months": calendar_months_for(
                events,
                reminders,
                today,
                current_month,
            ),
            "calendar_year": today.year,
            "weekdays": ["M", "T", "W", "T", "F", "S", "S"],
        },
    )


@login_required
def notifications(request):
    notification_items = list(Notification.objects.filter(
        recipient=request.user,
    ).select_related(
        "actor",
        "actor__profile",
        "event",
        "change_proposal",
        "change_proposal__event",
        "friend_request",
    ))
    unread_ids = [
        notification.id
        for notification in notification_items
        if not notification.is_read
    ]
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
    change_proposals = EventChangeProposal.objects.filter(
        event__owner=request.user,
        status=EventChangeProposal.Status.PENDING,
    ).select_related(
        "event",
        "proposed_by",
        "proposed_by__profile",
    ).order_by("-updated_at")
    invite_by_event_id = {
        invite.event_id: invite
        for invite in event_invites
    }
    friend_request_by_id = {
        friend_request.id: friend_request
        for friend_request in friend_requests
    }
    proposal_by_id = {
        proposal.id: proposal
        for proposal in change_proposals
    }

    for notification in notification_items:
        notification.action_invite = None
        notification.action_friend_request = None
        notification.action_proposal = None

        if notification.kind == Notification.Kind.EVENT_INVITE:
            notification.action_invite = invite_by_event_id.get(
                notification.event_id,
            )
        elif notification.kind == Notification.Kind.FRIEND_REQUEST:
            notification.action_friend_request = friend_request_by_id.get(
                notification.friend_request_id,
            )
        elif notification.kind == Notification.Kind.CHANGE_PROPOSED:
            notification.action_proposal = proposal_by_id.get(
                notification.change_proposal_id,
            )

    if unread_ids:
        Notification.objects.filter(
            id__in=unread_ids,
            recipient=request.user,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )

    return render(
        request,
        "planner/notifications.html",
        {
            "notifications": notification_items,
            "unread_count": len(unread_ids),
            "event_invites": event_invites,
            "friend_requests": friend_requests,
            "change_proposals": change_proposals,
        },
    )


@login_required
@require_POST
def notifications_mark_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(
        is_read=True,
        read_at=timezone.now(),
    )
    return redirect("notifications")


@login_required
@require_POST
def notification_delete(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
    )
    notification.delete()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return HttpResponse(status=204)

    return redirect("notifications")


@login_required
def event_detail(request, pk):
    friend_ids = accepted_friend_queryset(request.user).values("id")
    event = get_object_or_404(
        Event.objects.select_related("owner").filter(
            Q(owner=request.user)
            | Q(
                invites__invited_user=request.user,
                invites__status=EventInvite.Status.ACCEPTED,
            )
            | Q(
                owner_id__in=friend_ids,
                visibility=Event.Visibility.FRIENDS,
            )
        ).distinct(),
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
    is_owner = event.owner_id == request.user.id
    guest_invite = None
    guest_proposal = None

    if not is_owner:
        guest_invite = next(
            (
                invite
                for invite in event_invites
                if invite.invited_user_id == request.user.id
                and invite.status == EventInvite.Status.ACCEPTED
            ),
            None,
        )
        guest_proposal = event.change_proposals.filter(
            proposed_by=request.user,
            status=EventChangeProposal.Status.PENDING,
        ).first()

    return render(
        request,
        "planner/event_detail.html",
        {
            "event": event,
            "event_invites": event_invites,
            "is_owner": is_owner,
            "guest_invite": guest_invite,
            "guest_proposal": guest_proposal,
            "participants": participants,
            "proposal_cards": (
                change_proposal_cards(event, participants) if is_owner else []
            ),
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
        invited_users = [
            invite.invited_user
            for invite in event.invites.exclude(
                status=EventInvite.Status.DECLINED,
            ).select_related("invited_user")
        ]
        event_title = event.title
        Notification.objects.filter(
            event=event,
            kind=Notification.Kind.EVENT_INVITE,
        ).delete()
        event.delete()

        for invited_user in invited_users:
            notify_user(
                invited_user,
                Notification.Kind.EVENT_DELETED,
                f"{request.user.username} deleted an event",
                f"{event_title} was removed.",
                actor=request.user,
            )

        return redirect("home")

    return render(request, "planner/event_confirm_delete.html", {"event": event})


@login_required
def event_change_suggest(request, pk):
    event = get_object_or_404(
        Event.objects.filter(
            invites__invited_user=request.user,
            invites__status=EventInvite.Status.ACCEPTED,
        ).distinct(),
        pk=pk,
    )
    proposal = event.change_proposals.filter(
        proposed_by=request.user,
        status=EventChangeProposal.Status.PENDING,
    ).first()

    if request.method == "POST":
        is_new_proposal = proposal is None
        form = EventChangeProposalForm(
            request.POST,
            instance=proposal,
            user=request.user,
            event=event,
        )

        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.event = event
            proposal.proposed_by = request.user
            proposal.status = EventChangeProposal.Status.PENDING
            proposal.save()
            proposal.proposed_invitees.set(
                form.cleaned_data["invited_friends"]
            )
            notification_title = (
                f"{request.user.username} suggested changes"
                if is_new_proposal
                else f"{request.user.username} updated suggested changes"
            )
            notify_user(
                event.owner,
                Notification.Kind.CHANGE_PROPOSED,
                notification_title,
                f"{proposal.title} has a change request.",
                actor=request.user,
                event=event,
                change_proposal=proposal,
            )
            return redirect("event_detail", pk=event.pk)
    else:
        initial = None

        if proposal is None:
            initial = {
                "title": event.title,
                "description": event.description,
                "start_at": event.start_at,
                "end_at": event.end_at,
                "location": event.location,
            }

        form = EventChangeProposalForm(
            instance=proposal,
            initial=initial,
            user=request.user,
            event=event,
        )

    return render(
        request,
        "planner/event_change_form.html",
        {
            "event": event,
            "form": form,
            "proposal": proposal,
        },
    )


@login_required
@require_POST
def event_change_proposal_accept(request, pk):
    proposal = get_object_or_404(
        EventChangeProposal.objects.select_related("event"),
        pk=pk,
        event__owner=request.user,
        status=EventChangeProposal.Status.PENDING,
    )
    event = proposal.event

    with transaction.atomic():
        event.title = proposal.title
        event.description = proposal.description
        event.start_at = proposal.start_at
        event.end_at = proposal.end_at
        event.location = proposal.location
        event.save()

        for friend in proposal.proposed_invitees.exclude(pk=event.owner_id):
            invite, created = EventInvite.objects.get_or_create(
                event=event,
                invited_user=friend,
            )

            if not created and invite.status == EventInvite.Status.DECLINED:
                invite.status = EventInvite.Status.PENDING
                invite.save(update_fields=["status", "updated_at"])
                created = True

            if created:
                clear_action_notifications(
                    friend,
                    Notification.Kind.EVENT_INVITE,
                    event=event,
                )
                notify_user(
                    friend,
                    Notification.Kind.EVENT_INVITE,
                    f"{event.owner.username} invited you",
                    event.title,
                    actor=event.owner,
                    event=event,
                )

        proposal.status = EventChangeProposal.Status.ACCEPTED
        proposal.save(update_fields=["status", "updated_at"])

    clear_action_notifications(
        request.user,
        Notification.Kind.CHANGE_PROPOSED,
        change_proposal=proposal,
    )
    notify_user(
        proposal.proposed_by,
        Notification.Kind.CHANGE_ACCEPTED,
        f"{request.user.username} accepted your changes",
        event.title,
        actor=request.user,
        event=event,
        change_proposal=proposal,
    )

    return redirect("event_detail", pk=event.pk)


@login_required
@require_POST
def event_change_proposal_reject(request, pk):
    proposal = get_object_or_404(
        EventChangeProposal,
        pk=pk,
        event__owner=request.user,
        status=EventChangeProposal.Status.PENDING,
    )
    proposal.status = EventChangeProposal.Status.REJECTED
    proposal.save(update_fields=["status", "updated_at"])
    clear_action_notifications(
        request.user,
        Notification.Kind.CHANGE_PROPOSED,
        change_proposal=proposal,
    )
    notify_user(
        proposal.proposed_by,
        Notification.Kind.CHANGE_REJECTED,
        f"{request.user.username} rejected your changes",
        proposal.event.title,
        actor=request.user,
        event=proposal.event,
        change_proposal=proposal,
    )
    return redirect("event_detail", pk=proposal.event_id)


def event_visibility(form):
    if form.cleaned_data["is_group"]:
        return Event.Visibility.INVITE_ONLY
    return form.cleaned_data["visibility"]


def sync_event_invites(event, invited_friends, form):
    if not form.cleaned_data["is_group"]:
        invited_friends = []

    selected_ids = {friend.id for friend in invited_friends}

    removed_invites = list(EventInvite.objects.filter(event=event).exclude(
        invited_user_id__in=selected_ids,
    ).select_related("invited_user"))

    for invite in removed_invites:
        clear_action_notifications(
            invite.invited_user,
            Notification.Kind.EVENT_INVITE,
            event=event,
        )

    EventInvite.objects.filter(
        id__in=[invite.id for invite in removed_invites],
    ).delete()

    for friend in invited_friends:
        invite, created = EventInvite.objects.get_or_create(
            event=event,
            invited_user=friend,
        )

        if not created and invite.status == EventInvite.Status.DECLINED:
            invite.status = EventInvite.Status.PENDING
            invite.save()
            created = True

        if created:
            clear_action_notifications(
                friend,
                Notification.Kind.EVENT_INVITE,
                event=event,
            )
            notify_user(
                friend,
                Notification.Kind.EVENT_INVITE,
                f"{event.owner.username} invited you",
                event.title,
                actor=event.owner,
                event=event,
            )


@login_required
def reminder_create(request):
    if request.method == "POST":
        form = ReminderForm(request.POST)

        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.owner = request.user
            reminder.save()
            return redirect("home")
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
        return redirect("home")

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

    return redirect("home")


@login_required
def friends(request):
    context = friends_context(request.user)
    return render(request, "planner/friends.html", context)


def allowed_profile_users(user):
    return User.objects.filter(
        Q(
            received_friend_requests__from_user=user,
            received_friend_requests__status=FriendRequest.Status.ACCEPTED,
        )
        | Q(
            sent_friend_requests__to_user=user,
            sent_friend_requests__status=FriendRequest.Status.ACCEPTED,
        )
        | Q(
            sent_friend_requests__to_user=user,
            sent_friend_requests__status=FriendRequest.Status.PENDING,
        )
    ).distinct()


@login_required
def friend_profile_legacy(request, username):
    friend = get_object_or_404(
        allowed_profile_users(request.user),
        username=username,
    )
    return redirect("friend_profile", user_id=friend.id)


@login_required
def friend_profile(request, user_id):
    friend = get_object_or_404(
        allowed_profile_users(request.user).select_related("profile"),
        id=user_id,
    )
    today = timezone.localdate()
    (
        current_month,
        _first_month,
        _last_month_end,
        period_start,
        period_end,
    ) = calendar_period(today)
    shared_events = shared_events_between(request.user, friend)
    events = Event.objects.filter(
        Q(
            owner=friend,
            visibility=Event.Visibility.FRIENDS,
        )
        | Q(pk__in=shared_events.values("pk")),
        start_at__gte=period_start,
        start_at__lt=period_end,
    ).select_related(
        "owner",
        "owner__profile",
    ).prefetch_related(
        Prefetch("invites", queryset=active_event_invites(), to_attr="active_invites")
    ).order_by("start_at")

    return render(
        request,
        "planner/friend_profile.html",
        {
            "profile_user": friend,
            "public_event_count": Event.objects.filter(
                owner=friend,
                visibility=Event.Visibility.FRIENDS,
            ).count(),
            "shared_event_count": shared_events.count(),
            "calendar_months": calendar_months_for(
                events,
                [],
                today,
                current_month,
            ),
            "calendar_year": today.year,
            "weekdays": ["M", "T", "W", "T", "F", "S", "S"],
        },
    )


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
    friends = accepted_friend_queryset(user).select_related("profile")
    current_time = timezone.now()
    friend_cards = []

    for friend in friends:
        shared_events = shared_events_between(user, friend).filter(
            Q(end_at__gte=current_time)
            | Q(end_at__isnull=True, start_at__gte=current_time)
        ).select_related(
            "owner",
            "owner__profile",
        ).prefetch_related(
            Prefetch(
                "invites",
                queryset=active_event_invites(),
                to_attr="active_invites",
            )
        ).order_by("-start_at")
        friend_cards.append(
            {
                "friend": friend,
                "shared_event_cards": event_cards(shared_events),
            }
        )

    return {
        "form": form or FriendRequestForm(),
        "friend_cards": friend_cards,
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
            else:
                outgoing_request = FriendRequest.objects.filter(
                    from_user=request.user,
                    to_user=to_user,
                ).first()
                incoming_request = FriendRequest.objects.filter(
                    from_user=to_user,
                    to_user=request.user,
                ).first()

                accepted_request = (
                    outgoing_request
                    and outgoing_request.status == FriendRequest.Status.ACCEPTED
                ) or (
                    incoming_request
                    and incoming_request.status == FriendRequest.Status.ACCEPTED
                )

                if accepted_request:
                    form.add_error("username", "You are already friends.")
                elif (
                    incoming_request
                    and incoming_request.status == FriendRequest.Status.PENDING
                ):
                    incoming_request.status = FriendRequest.Status.ACCEPTED
                    incoming_request.save(update_fields=["status", "updated_at"])
                    clear_action_notifications(
                        request.user,
                        Notification.Kind.FRIEND_REQUEST,
                        friend_request=incoming_request,
                    )

                    if outgoing_request:
                        outgoing_request.delete()

                    notify_user(
                        to_user,
                        Notification.Kind.FRIEND_ACCEPTED,
                        f"{request.user.username} accepted your request",
                        "You are friends now.",
                        actor=request.user,
                        friend_request=incoming_request,
                    )

                    return redirect("friends")
                elif (
                    outgoing_request
                    and outgoing_request.status == FriendRequest.Status.PENDING
                ):
                    form.add_error("username", "Friend request already exists.")
                else:
                    friend_request, _created = FriendRequest.objects.update_or_create(
                        from_user=request.user,
                        to_user=to_user,
                        defaults={"status": FriendRequest.Status.PENDING},
                    )
                    notify_user(
                        to_user,
                        Notification.Kind.FRIEND_REQUEST,
                        f"{request.user.username} sent a friend request",
                        "Open Friends to accept or reject it.",
                        actor=request.user,
                        friend_request=friend_request,
                    )
                    return redirect("friends")
    else:
        form = FriendRequestForm()

    return render(request, "planner/friend_form.html", {"form": form})


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
    clear_action_notifications(
        request.user,
        Notification.Kind.FRIEND_REQUEST,
        friend_request=friend_request,
    )
    notify_user(
        friend_request.from_user,
        Notification.Kind.FRIEND_ACCEPTED,
        f"{request.user.username} accepted your request",
        "You are friends now.",
        actor=request.user,
        friend_request=friend_request,
    )
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
    clear_action_notifications(
        request.user,
        Notification.Kind.FRIEND_REQUEST,
        friend_request=friend_request,
    )
    return redirect("friends")


@login_required
@require_POST
def friend_request_cancel(request, pk):
    friend_request = get_object_or_404(
        FriendRequest,
        pk=pk,
        from_user=request.user,
        status=FriendRequest.Status.PENDING,
    )
    clear_action_notifications(
        friend_request.to_user,
        Notification.Kind.FRIEND_REQUEST,
        friend_request=friend_request,
    )
    friend_request.delete()
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
    clear_action_notifications(
        request.user,
        Notification.Kind.EVENT_INVITE,
        event=invite.event,
    )
    notify_user(
        invite.event.owner,
        Notification.Kind.EVENT_INVITE_ACCEPTED,
        f"{request.user.username} joined your event",
        invite.event.title,
        actor=request.user,
        event=invite.event,
    )
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
    clear_action_notifications(
        request.user,
        Notification.Kind.EVENT_INVITE,
        event=invite.event,
    )
    notify_user(
        invite.event.owner,
        Notification.Kind.EVENT_INVITE_DECLINED,
        f"{request.user.username} declined your event",
        invite.event.title,
        actor=request.user,
        event=invite.event,
    )
    return redirect("home")


@login_required
@require_POST
def event_invite_leave(request, pk):
    invite = get_object_or_404(
        EventInvite,
        pk=pk,
        invited_user=request.user,
        status=EventInvite.Status.ACCEPTED,
    )
    EventChangeProposal.objects.filter(
        event=invite.event,
        proposed_by=request.user,
        status=EventChangeProposal.Status.PENDING,
    ).update(status=EventChangeProposal.Status.REJECTED)
    invite.status = EventInvite.Status.DECLINED
    invite.save(update_fields=["status", "updated_at"])
    notify_user(
        invite.event.owner,
        Notification.Kind.EVENT_LEFT,
        f"{request.user.username} left your event",
        invite.event.title,
        actor=request.user,
        event=invite.event,
    )
    return redirect("home")
