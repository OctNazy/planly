import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Profile
from .telegram import TelegramAuthError, validate_telegram_init_data

MAX_TELEGRAM_AVATAR_BYTES = 3 * 1024 * 1024


def unique_telegram_username(telegram_user):
    base_username = telegram_user.username or f"telegram_{telegram_user.telegram_id}"
    username = base_username[:150]
    counter = 1

    while User.objects.filter(username=username).exists():
        suffix = f"_{counter}"
        username = f"{base_username[:150 - len(suffix)]}{suffix}"
        counter += 1

    return username


def initialize_telegram_profile(profile, telegram_user):
    profile.telegram_id = telegram_user.telegram_id
    profile.telegram_username = telegram_user.username
    profile.telegram_chat_id = telegram_user.telegram_id
    profile.telegram_photo_url = telegram_user.photo_url
    profile.save(
        update_fields=[
            "telegram_id",
            "telegram_username",
            "telegram_chat_id",
            "telegram_photo_url",
        ]
    )
    save_telegram_avatar(profile, telegram_user)


def avatar_extension(image_content, photo_url):
    if image_content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image_content.startswith(b"\x89PNG"):
        return ".png"
    if image_content.startswith(b"RIFF") and image_content[8:12] == b"WEBP":
        return ".webp"

    stripped_content = image_content.lstrip()
    if stripped_content.startswith((b"<svg", b"<?xml")):
        return ".svg"

    url_extension = Path(photo_url).suffix.lower()
    if url_extension in [".jpg", ".jpeg", ".png", ".webp", ".svg"]:
        return url_extension

    return ".jpg"


def telegram_avatar_name(profile, photo_url, image_content):
    extension = avatar_extension(image_content, photo_url)
    return f"telegram_{profile.user_id}_{profile.telegram_id}{extension}"


def download_telegram_avatar(photo_url):
    with urlopen(photo_url, timeout=5) as response:
        return response.read(MAX_TELEGRAM_AVATAR_BYTES + 1)


def save_telegram_avatar(profile, telegram_user):
    if profile.avatar or not telegram_user.photo_url:
        return

    try:
        image_content = download_telegram_avatar(telegram_user.photo_url)
    except (OSError, URLError):
        return

    if len(image_content) > MAX_TELEGRAM_AVATAR_BYTES:
        return

    profile.avatar.save(
        telegram_avatar_name(profile, telegram_user.photo_url, image_content),
        ContentFile(image_content),
        save=True,
    )


def get_or_create_telegram_user(telegram_user):
    profile = Profile.objects.select_related("user").filter(
        telegram_id=telegram_user.telegram_id,
    ).first()

    if profile:
        return profile.user

    username = unique_telegram_username(telegram_user)
    user = User(
        username=username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
    )
    user.set_unusable_password()
    user.save()

    profile = Profile.objects.create(user=user)
    initialize_telegram_profile(profile, telegram_user)
    return user


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "accounts/register.html", {"form": form})


def telegram_entry(request):
    return render(request, "accounts/telegram_entry.html")


@csrf_exempt
@require_POST
def telegram_auth(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        telegram_user = validate_telegram_init_data(payload.get("init_data", ""))

        with transaction.atomic():
            user = get_or_create_telegram_user(telegram_user)
            login(request, user)

    except (json.JSONDecodeError, KeyError, TelegramAuthError, IntegrityError) as error:
        return JsonResponse({"ok": False, "error": str(error)}, status=400)

    return JsonResponse({"ok": True, "redirect_url": "/"})
