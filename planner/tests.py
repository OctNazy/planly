from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Event, Reminder


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

    def test_user_cannot_open_other_user_event(self):
        event = Event.objects.create(
            owner=self.other_user,
            title="Private plan",
            start_at="2026-07-10T18:00Z",
        )
        self.client.login(username="nazar", password="testpass123")

        response = self.client.get(reverse("event_detail", args=[event.pk]))

        self.assertEqual(response.status_code, 404)

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
