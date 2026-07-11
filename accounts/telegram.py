import hashlib
import hmac
import json
from dataclasses import dataclass
from time import time
from urllib.parse import parse_qsl

from django.conf import settings


class TelegramAuthError(ValueError):
    pass


@dataclass
class TelegramUserData:
    telegram_id: int
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    photo_url: str = ""


def validate_telegram_init_data(init_data):
    bot_token = settings.TELEGRAM_BOT_TOKEN

    if not bot_token:
        raise TelegramAuthError("Telegram bot token is not configured.")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")

    if not received_hash:
        raise TelegramAuthError("Telegram auth hash is missing.")

    try:
        auth_date = int(values.get("auth_date", "0") or "0")
    except ValueError as error:
        raise TelegramAuthError("Telegram auth date is invalid.") from error

    max_age = settings.TELEGRAM_AUTH_MAX_AGE_SECONDS

    if max_age and time() - auth_date > max_age:
        raise TelegramAuthError("Telegram auth data is too old.")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramAuthError("Telegram auth hash is invalid.")

    raw_user = values.get("user")

    if not raw_user:
        raise TelegramAuthError("Telegram user data is missing.")

    user_data = json.loads(raw_user)
    return TelegramUserData(
        telegram_id=int(user_data["id"]),
        username=user_data.get("username", ""),
        first_name=user_data.get("first_name", ""),
        last_name=user_data.get("last_name", ""),
        photo_url=user_data.get("photo_url", ""),
    )
