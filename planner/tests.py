from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import (
    Event,
    EventChangeProposal,
    EventInvite,
    FriendRequest,
    Notification,
    Reminder,
)


class EventViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="nazar",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            username="friend",
            password="testpass123",
        )

    def test_home_requires_login(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_user_can_create_event(self):
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("event_create"),
            {
                "title": "Fly to Warsaw",
                "description": "Evening flight",
                "start_at": "2026-07-10T18:00",
                "end_at": "2026-07-10T21:00",
                "location": "Airport",
                "visibility": Event.Visibility.FRIENDS,
            },
        )

        self.assertEqual(response.status_code, 302)
        event = Event.objects.get(
            owner=self.user,
            title="Fly to Warsaw",
        )
        self.assertEqual(event.visibility, Event.Visibility.FRIENDS)

    def test_user_cannot_create_event_with_end_before_start(self):
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("event_create"),
            {
                "title": "Wrong time",
                "description": "",
                "start_at": "2026-07-10T18:00",
                "end_at": "2026-07-10T17:00",
                "location": "",
                "visibility": Event.Visibility.PRIVATE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "End time must be after start time.")
        self.assertFalse(Event.objects.filter(title="Wrong time").exists())

    def test_event_create_page_shows_group_picker(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=FriendRequest.Status.ACCEPTED,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("event_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Group event")
        self.assertContains(response, "friend")

    def test_user_cannot_open_other_user_event(self):
        event = Event.objects.create(
            owner=self.other_user,
            title="Private plan",
            start_at="2026-07-10T18:00Z",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("event_detail", args=[event.pk]))

        self.assertEqual(response.status_code, 404)

    def test_owner_can_invite_friend_when_creating_event(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=FriendRequest.Status.ACCEPTED,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("event_create"),
            {
                "title": "Pizza night",
                "description": "Friday plan",
                "start_at": "2026-07-10T18:00",
                "end_at": "",
                "location": "City center",
                "visibility": Event.Visibility.PRIVATE,
                "is_group": "on",
                "invited_friends": [self.other_user.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            EventInvite.objects.filter(
                event__owner=self.user,
                event__title="Pizza night",
                invited_user=self.other_user,
                status=EventInvite.Status.PENDING,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.other_user,
                actor=self.user,
                kind=Notification.Kind.EVENT_INVITE,
                title__contains="invited",
            ).exists()
        )

    def test_accepted_invited_event_appears_on_home(self):
        event = Event.objects.create(
            owner=self.user,
            title="Group dinner",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
            status=EventInvite.Status.ACCEPTED,
        )
        self.client.login(username="friend", password="testpass123")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Group dinner")
        self.assertNotContains(response, "Shared with you")

    def test_calendar_marks_days_with_events(self):
        Event.objects.create(
            owner=self.user,
            title="Calendar event",
            start_at="2026-07-10T18:00Z",
        )
        Reminder.objects.create(
            owner=self.user,
            title="Calendar reminder",
            remind_date="2026-07-10",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("calendar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2026")
        self.assertContains(response, "Jul")
        self.assertContains(response, "calendar-scroll")
        self.assertContains(response, 'id="current-month"')
        self.assertContains(response, "event-dots")
        self.assertContains(response, "reminder-dots")
        self.assertContains(response, 'data-day-target="day-plan-2026-07-10"')
        self.assertContains(response, 'id="day-plan-2026-07-10"')
        self.assertContains(response, "Calendar event")
        self.assertContains(response, "Calendar reminder")

    def test_invited_user_can_accept_event_invite(self):
        event = Event.objects.create(
            owner=self.user,
            title="Pizza night",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        invite = EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
        )
        action_notification = Notification.objects.create(
            recipient=self.other_user,
            actor=self.user,
            kind=Notification.Kind.EVENT_INVITE,
            title="nazar invited you",
            event=event,
        )
        self.client.login(username="friend", password="testpass123")

        response = self.client.post(reverse("event_invite_accept", args=[invite.pk]))
        invite.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(invite.status, EventInvite.Status.ACCEPTED)
        self.assertFalse(
            Notification.objects.filter(pk=action_notification.pk).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.user,
                actor=self.other_user,
                kind=Notification.Kind.EVENT_INVITE_ACCEPTED,
            ).exists()
        )

    def test_invited_user_can_open_accepted_event(self):
        event = Event.objects.create(
            owner=self.user,
            title="Pizza night",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
            status=EventInvite.Status.ACCEPTED,
        )
        self.client.login(username="friend", password="testpass123")

        response = self.client.get(reverse("event_detail", args=[event.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pizza night")

    def test_owner_can_open_event_with_multiple_invites(self):
        third_user = User.objects.create_user(
            username="third",
            password="testpass123",
        )
        event = Event.objects.create(
            owner=self.user,
            title="Group dinner",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
            status=EventInvite.Status.ACCEPTED,
        )
        EventInvite.objects.create(
            event=event,
            invited_user=third_user,
            status=EventInvite.Status.PENDING,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("event_detail", args=[event.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Group dinner")

    def test_guest_can_leave_group_event(self):
        event = Event.objects.create(
            owner=self.user,
            title="Pizza night",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        invite = EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
            status=EventInvite.Status.ACCEPTED,
        )
        self.client.login(username="friend", password="testpass123")

        response = self.client.post(
            reverse("event_invite_leave", args=[invite.pk])
        )
        invite.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(invite.status, EventInvite.Status.DECLINED)
        self.assertEqual(
            self.client.get(reverse("event_detail", args=[event.pk])).status_code,
            404,
        )

    def test_guest_can_propose_event_changes_and_invite_friend(self):
        third_user = User.objects.create_user(
            username="third",
            password="testpass123",
        )
        FriendRequest.objects.create(
            from_user=self.other_user,
            to_user=third_user,
            status=FriendRequest.Status.ACCEPTED,
        )
        event = Event.objects.create(
            owner=self.user,
            title="Pizza night",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
            status=EventInvite.Status.ACCEPTED,
        )
        self.client.login(username="friend", password="testpass123")

        response = self.client.post(
            reverse("event_change_suggest", args=[event.pk]),
            {
                "title": "Dinner downtown",
                "description": "Try a new place",
                "start_at": "2026-07-10T19:00",
                "end_at": "2026-07-10T21:00",
                "location": "Old Town",
                "invited_friends": [third_user.pk],
            },
        )
        proposal = EventChangeProposal.objects.get(
            event=event,
            proposed_by=self.other_user,
        )
        event.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(proposal.title, "Dinner downtown")
        self.assertEqual(
            list(proposal.proposed_invitees.all()),
            [third_user],
        )
        self.assertEqual(event.title, "Pizza night")
        self.assertFalse(
            EventInvite.objects.filter(
                event=event,
                invited_user=third_user,
            ).exists()
        )

    def test_owner_sees_change_proposal_notification(self):
        event = Event.objects.create(
            owner=self.user,
            title="Pizza night",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        proposal = EventChangeProposal.objects.create(
            event=event,
            proposed_by=self.other_user,
            title="Dinner downtown",
            start_at="2026-07-10T19:00Z",
        )
        Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.CHANGE_PROPOSED,
            title="friend suggested changes",
            event=event,
            change_proposal=proposal,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("notifications"))
        detail_response = self.client.get(
            reverse("event_detail", args=[event.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pizza night")
        self.assertContains(response, "Changes suggested by friend")
        self.assertContains(response, "View")
        self.assertContains(response, f"#proposal-{proposal.pk}")
        self.assertContains(detail_response, "Changes from friend")
        self.assertContains(detail_response, "proposal-changed")

    def test_owner_can_accept_event_change_proposal(self):
        third_user = User.objects.create_user(
            username="third",
            password="testpass123",
        )
        event = Event.objects.create(
            owner=self.user,
            title="Pizza night",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.INVITE_ONLY,
        )
        proposal = EventChangeProposal.objects.create(
            event=event,
            proposed_by=self.other_user,
            title="Dinner downtown",
            description="Try a new place",
            start_at="2026-07-10T19:00Z",
            end_at="2026-07-10T21:00Z",
            location="Old Town",
        )
        proposal.proposed_invitees.add(third_user)
        action_notification = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.CHANGE_PROPOSED,
            title="friend suggested changes",
            event=event,
            change_proposal=proposal,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("event_change_proposal_accept", args=[proposal.pk])
        )
        event.refresh_from_db()
        proposal.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(event.title, "Dinner downtown")
        self.assertEqual(event.location, "Old Town")
        self.assertEqual(proposal.status, EventChangeProposal.Status.ACCEPTED)
        self.assertFalse(
            Notification.objects.filter(pk=action_notification.pk).exists()
        )
        self.assertTrue(
            EventInvite.objects.filter(
                event=event,
                invited_user=third_user,
                status=EventInvite.Status.PENDING,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.other_user,
                actor=self.user,
                kind=Notification.Kind.CHANGE_ACCEPTED,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=third_user,
                actor=self.user,
                kind=Notification.Kind.EVENT_INVITE,
            ).exists()
        )

    def test_user_can_create_reminder(self):
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("reminder_create"),
            {
                "title": "Call grandma",
                "note": "Birthday reminder",
                "remind_date": "2026-07-12",
                "remind_time": "10:00",
                "repeat": Reminder.Repeat.YEARLY,
                "remove_mode": Reminder.RemoveMode.KEEP_UNTIL_DONE,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Reminder.objects.filter(
                owner=self.user,
                title="Call grandma",
            ).exists()
        )

    def test_user_can_mark_reminder_done(self):
        reminder = Reminder.objects.create(
            owner=self.user,
            title="Pay internet",
            remind_date="2026-07-12",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(reverse("reminder_done", args=[reminder.pk]))
        reminder.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(reminder.is_done)

    def test_user_can_open_own_reminder(self):
        reminder = Reminder.objects.create(
            owner=self.user,
            title="Call grandma",
            remind_date="2026-07-12",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("reminder_detail", args=[reminder.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Call grandma")

    def test_user_cannot_open_other_user_reminder(self):
        reminder = Reminder.objects.create(
            owner=self.other_user,
            title="Private reminder",
            remind_date="2026-07-12",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("reminder_detail", args=[reminder.pk]))

        self.assertEqual(response.status_code, 404)

    def test_user_can_edit_own_reminder(self):
        reminder = Reminder.objects.create(
            owner=self.user,
            title="Pay internet",
            remind_date="2026-07-12",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("reminder_update", args=[reminder.pk]),
            {
                "title": "Pay rent",
                "note": "Before evening",
                "remind_date": "2026-07-13",
                "remind_time": "12:00",
                "repeat": Reminder.Repeat.NONE,
                "remove_mode": Reminder.RemoveMode.KEEP_UNTIL_DONE,
            },
        )
        reminder.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(reminder.title, "Pay rent")
        self.assertEqual(reminder.note, "Before evening")

    def test_user_cannot_edit_other_user_reminder(self):
        reminder = Reminder.objects.create(
            owner=self.other_user,
            title="Private reminder",
            remind_date="2026-07-12",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("reminder_update", args=[reminder.pk]),
            {
                "title": "Changed title",
                "note": "",
                "remind_date": "2026-07-13",
                "remind_time": "",
                "repeat": Reminder.Repeat.NONE,
                "remove_mode": Reminder.RemoveMode.KEEP_UNTIL_DONE,
            },
        )
        reminder.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(reminder.title, "Private reminder")

    def test_reminder_delete_requires_post(self):
        reminder = Reminder.objects.create(
            owner=self.user,
            title="Pay internet",
            remind_date="2026-07-12",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("reminder_delete", args=[reminder.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Reminder.objects.filter(pk=reminder.pk).exists())

    def test_user_can_delete_own_reminder(self):
        reminder = Reminder.objects.create(
            owner=self.user,
            title="Pay internet",
            remind_date="2026-07-12",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(reverse("reminder_delete", args=[reminder.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Reminder.objects.filter(pk=reminder.pk).exists())

    def test_user_can_send_friend_request(self):
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("friend_request_create"),
            {"username": "friend"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FriendRequest.objects.filter(
                from_user=self.user,
                to_user=self.other_user,
                status=FriendRequest.Status.PENDING,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.other_user,
                actor=self.user,
                kind=Notification.Kind.FRIEND_REQUEST,
            ).exists()
        )

    def test_mutual_friend_request_is_accepted_automatically(self):
        friend_request = FriendRequest.objects.create(
            from_user=self.other_user,
            to_user=self.user,
        )
        action_notification = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.FRIEND_REQUEST,
            title="friend sent a friend request",
            friend_request=friend_request,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("friend_request_create"),
            {"username": "friend"},
        )
        friend_request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(friend_request.status, FriendRequest.Status.ACCEPTED)
        self.assertFalse(
            Notification.objects.filter(pk=action_notification.pk).exists()
        )
        self.assertEqual(
            FriendRequest.objects.filter(
                Q(from_user=self.user, to_user=self.other_user)
                | Q(from_user=self.other_user, to_user=self.user)
            ).count(),
            1,
        )

    def test_user_cannot_send_friend_request_to_self(self):
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("friend_request_create"),
            {"username": "nazar"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(FriendRequest.objects.exists())
        self.assertContains(response, "You cannot add yourself.")

    def test_user_can_accept_incoming_friend_request(self):
        friend_request = FriendRequest.objects.create(
            from_user=self.other_user,
            to_user=self.user,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("friend_request_accept", args=[friend_request.pk])
        )
        friend_request.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(friend_request.status, FriendRequest.Status.ACCEPTED)

    def test_user_cannot_accept_other_user_friend_request(self):
        third_user = User.objects.create_user(
            username="third",
            password="testpass123",
        )
        friend_request = FriendRequest.objects.create(
            from_user=self.other_user,
            to_user=third_user,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("friend_request_accept", args=[friend_request.pk])
        )
        friend_request.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(friend_request.status, FriendRequest.Status.PENDING)

    def test_user_can_cancel_sent_friend_request(self):
        friend_request = FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other_user,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("friend_request_cancel", args=[friend_request.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            FriendRequest.objects.filter(pk=friend_request.pk).exists()
        )

    def test_friend_profile_shows_only_events_visible_to_friends(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=FriendRequest.Status.ACCEPTED,
        )
        Event.objects.create(
            owner=self.other_user,
            title="Public meetup",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.FRIENDS,
        )
        Event.objects.create(
            owner=self.other_user,
            title="Private appointment",
            start_at="2026-07-11T18:00Z",
            visibility=Event.Visibility.PRIVATE,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(
            reverse("friend_profile", args=[self.other_user.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public meetup")
        self.assertNotContains(response, "Private appointment")
        self.assertContains(response, "compact-calendar-shell")

    def test_friend_profile_shows_shared_group_event(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=FriendRequest.Status.ACCEPTED,
        )
        event = Event.objects.create(
            owner=self.user,
            title="Trip together",
            start_at=timezone.now() + timedelta(days=1),
            visibility=Event.Visibility.INVITE_ONLY,
        )
        EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
            status=EventInvite.Status.ACCEPTED,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(
            reverse("friend_profile", args=[self.other_user.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trip together")

    def test_friends_page_previews_upcoming_shared_events(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=FriendRequest.Status.ACCEPTED,
        )
        event = Event.objects.create(
            owner=self.user,
            title="Trip together",
            start_at=timezone.now() + timedelta(days=1),
            visibility=Event.Visibility.INVITE_ONLY,
        )
        EventInvite.objects.create(
            event=event,
            invited_user=self.other_user,
            status=EventInvite.Status.ACCEPTED,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("friends"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upcoming together")
        self.assertContains(response, "Trip together")
        self.assertContains(response, "friend-shared-scroll")

    def test_non_friend_cannot_open_friend_profile(self):
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(
            reverse("friend_profile", args=[self.other_user.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_user_can_open_pending_request_sender_profile(self):
        FriendRequest.objects.create(
            from_user=self.other_user,
            to_user=self.user,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(
            reverse("friend_profile", args=[self.other_user.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "friend")

    def test_friend_can_open_shared_event_but_not_private_event(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=FriendRequest.Status.ACCEPTED,
        )
        shared_event = Event.objects.create(
            owner=self.other_user,
            title="Public meetup",
            start_at="2026-07-10T18:00Z",
            visibility=Event.Visibility.FRIENDS,
        )
        private_event = Event.objects.create(
            owner=self.other_user,
            title="Private appointment",
            start_at="2026-07-11T18:00Z",
            visibility=Event.Visibility.PRIVATE,
        )
        self.client.login(username="nazar", password="testpass123")

        shared_response = self.client.get(
            reverse("event_detail", args=[shared_event.pk])
        )
        private_response = self.client.get(
            reverse("event_detail", args=[private_event.pk])
        )

        self.assertEqual(shared_response.status_code, 200)
        self.assertEqual(private_response.status_code, 404)

    def test_user_can_mark_notifications_as_read(self):
        Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.FRIEND_REQUEST,
            title="friend sent a friend request",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(reverse("notifications_mark_read"))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.user,
                is_read=False,
            ).exists()
        )

    def test_notifications_are_marked_seen_after_page_view(self):
        notification = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.FRIEND_ACCEPTED,
            title="friend accepted your request",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("notifications"))
        notification.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="notification-card unread-notification"')
        self.assertTrue(notification.is_read)

        second_response = self.client.get(reverse("notifications"))
        self.assertNotContains(
            second_response,
            'class="notification-card unread-notification"',
        )

    def test_friend_request_notification_links_to_sender_profile(self):
        friend_request = FriendRequest.objects.create(
            from_user=self.other_user,
            to_user=self.user,
        )
        Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.FRIEND_REQUEST,
            title="friend sent a friend request",
            friend_request=friend_request,
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("friend_profile", args=[self.other_user.id]),
        )

    def test_user_can_delete_own_notification(self):
        notification = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.FRIEND_REQUEST,
            title="friend sent a friend request",
        )
        other_notification = Notification.objects.create(
            recipient=self.other_user,
            actor=self.user,
            kind=Notification.Kind.FRIEND_REQUEST,
            title="nazar sent a friend request",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("notification_delete", args=[notification.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())
        self.assertTrue(
            Notification.objects.filter(pk=other_notification.pk).exists()
        )

    def test_ajax_notification_delete_does_not_redirect(self):
        notification = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            kind=Notification.Kind.FRIEND_ACCEPTED,
            title="friend accepted your request",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.post(
            reverse("notification_delete", args=[notification.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())
