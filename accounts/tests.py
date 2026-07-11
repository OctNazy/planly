import hashlib
import hmac
import json
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Profile


def telegram_init_data(bot_token, user_data, auth_date=1783770000):
    values = {
        "auth_date": str(auth_date),
        "query_id": "test-query",
        "user": json.dumps(user_data, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


@override_settings(
    TELEGRAM_BOT_TOKEN="123:test-token",
    TELEGRAM_AUTH_MAX_AGE_SECONDS=0,
)
class TelegramAuthTests(TestCase):
    def test_register_redirects_to_home(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new_user",
                "password1": "testpass123",
                "password2": "testpass123",
            },
        )

        self.assertRedirects(response, reverse("home"))

    def test_telegram_entry_is_public(self):
        response = self.client.get(reverse("telegram_entry"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opening Planly")

    def test_telegram_auth_creates_and_logs_in_user(self):
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1001,
                "username": "telegram_nazar",
                "first_name": "Nazar",
                "last_name": "Dubil",
                "photo_url": "https://example.com/avatar.jpg",
            },
        )

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        profile = Profile.objects.select_related("user").get(telegram_id=1001)
        self.assertEqual(profile.user.username, "telegram_nazar")
        self.assertEqual(profile.telegram_chat_id, 1001)
        self.assertEqual(profile.telegram_photo_url, "https://example.com/avatar.jpg")
        self.assertEqual(int(self.client.session["_auth_user_id"]), profile.user.id)

    def test_telegram_auth_prefers_telegram_user_over_existing_session(self):
        admin = User.objects.create_user(username="OctoNaz")
        old_user = User.objects.create_user(username="Nazik663", password="testpass123")
        Profile.objects.create(
            user=admin,
            telegram_id=1004,
            telegram_username="Nazik663",
            telegram_chat_id=1004,
        )
        Profile.objects.create(user=old_user)
        self.client.login(username="Nazik663", password="testpass123")
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1004,
                "username": "Nazik663",
            },
        )

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), admin.id)
        self.assertIsNone(Profile.objects.get(user=old_user).telegram_id)

    def test_telegram_auth_rejects_invalid_hash(self):
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1002,
                "username": "bad_hash",
            },
        ).replace("hash=", "hash=broken")

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Profile.objects.filter(telegram_id=1002).exists())

    def test_telegram_auth_rejects_invalid_auth_date(self):
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1003,
                "username": "bad_date",
            },
            auth_date="not-a-number",
        )

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Profile.objects.filter(telegram_id=1003).exists())
