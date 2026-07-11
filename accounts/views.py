import json

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Profile
from .telegram import TelegramAuthError, validate_telegram_init_data


def unique_telegram_username(telegram_user):
    base_username = telegram_user.username or f"telegram_{telegram_user.telegram_id}"
    username = base_username[:150]
    counter = 1

    while User.objects.filter(username=username).exists():
        suffix = f"_{counter}"
        username = f"{base_username[:150 - len(suffix)]}{suffix}"
        counter += 1

    return username


def apply_telegram_profile(profile, telegram_user):
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


def get_or_create_telegram_user(telegram_user):
    profile = Profile.objects.select_related("user").filter(
        telegram_id=telegram_user.telegram_id,
    ).first()

    if profile:
        apply_telegram_profile(profile, telegram_user)
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
    apply_telegram_profile(profile, telegram_user)
    return user


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("event_list")
    else:
        form = UserCreationForm()

    return render(request, "accounts/register.html", {"form": form})


@csrf_exempt
@require_POST
def telegram_auth(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        telegram_user = validate_telegram_init_data(payload.get("init_data", ""))

        with transaction.atomic():
            if request.user.is_authenticated:
                profile, _ = Profile.objects.get_or_create(user=request.user)
                apply_telegram_profile(profile, telegram_user)
                user = request.user
            else:
                user = get_or_create_telegram_user(telegram_user)

            login(request, user)

    except (json.JSONDecodeError, KeyError, TelegramAuthError, IntegrityError) as error:
        return JsonResponse({"ok": False, "error": str(error)}, status=400)

    return JsonResponse({"ok": True, "redirect_url": "/"})
