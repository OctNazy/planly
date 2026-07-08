from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Event, EventInvite, FriendRequest, Reminder


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

    def test_event_list_requires_login(self):
        response = self.client.get(reverse("event_list"))

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
                "visibility": Event.Visibility.PRIVATE,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Event.objects.filter(
                owner=self.user,
                title="Fly to Warsaw",
            ).exists()
        )

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
                "visibility": Event.Visibility.INVITE_ONLY,
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

    def test_accepted_invited_event_appears_in_main_event_list(self):
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

        response = self.client.get(reverse("event_list"))

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
        self.client.login(username="friend", password="testpass123")

        response = self.client.post(reverse("event_invite_accept", args=[invite.pk]))
        invite.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(invite.status, EventInvite.Status.ACCEPTED)

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
