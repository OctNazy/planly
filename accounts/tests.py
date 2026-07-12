import hashlib
import hmac
import json
from urllib.parse import urlencode
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
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

    @patch("accounts.views.download_telegram_avatar", return_value=b"fake-image")
    def test_telegram_auth_creates_and_logs_in_user(self, _download_avatar):
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

    @patch("accounts.views.download_telegram_avatar", return_value=b"fake-image")
    def test_telegram_auth_saves_photo_as_avatar(self, _download_avatar):
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1005,
                "username": "avatar_user",
                "photo_url": "https://example.com/avatar.jpg",
            },
        )

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        profile = Profile.objects.get(telegram_id=1005)
        self.assertTrue(profile.avatar.name.startswith("avatars/telegram_"))
        self.assertTrue(profile.avatar.name.endswith(".jpg"))

    @patch("accounts.views.download_telegram_avatar", return_value=b"\xff\xd8\xfffake-jpg")
    def test_telegram_auth_uses_real_avatar_format_over_url_extension(self, _download_avatar):
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1008,
                "username": "jpg_disguised_as_svg",
                "photo_url": "https://example.com/avatar.svg",
            },
        )

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        profile = Profile.objects.get(telegram_id=1008)
        self.assertTrue(profile.avatar.name.startswith("avatars/telegram_"))
        self.assertTrue(profile.avatar.name.endswith(".jpg"))

    @patch("accounts.views.download_telegram_avatar", return_value=b"fake-image")
    def test_telegram_auth_does_not_replace_existing_avatar(self, _download_avatar):
        user = User.objects.create_user(username="avatar_owner")
        profile = Profile.objects.create(user=user, telegram_id=1006)
        profile.avatar.save("avatars/manual.jpg", ContentFile(b"manual"), save=True)
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1006,
                "username": "avatar_owner",
                "photo_url": "https://example.com/avatar.jpg",
            },
        )

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertIn("avatars/manual", profile.avatar.name)
        _download_avatar.assert_not_called()

    @patch("accounts.views.download_telegram_avatar", return_value=b"fake-image")
    def test_telegram_auth_does_not_sync_existing_profile_data(self, _download_avatar):
        user = User.objects.create_user(username="existing_user")
        profile = Profile.objects.create(
            user=user,
            telegram_id=1007,
            telegram_username="old_username",
            telegram_chat_id=1007,
            telegram_photo_url="https://example.com/old.jpg",
        )
        init_data = telegram_init_data(
            "123:test-token",
            {
                "id": 1007,
                "username": "new_username",
                "photo_url": "https://example.com/new.jpg",
            },
        )

        response = self.client.post(
            reverse("telegram_auth"),
            data=json.dumps({"init_data": init_data}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.telegram_username, "old_username")
        self.assertEqual(profile.telegram_photo_url, "https://example.com/old.jpg")
        self.assertFalse(profile.avatar)
        _download_avatar.assert_not_called()

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
