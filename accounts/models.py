from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_username = models.CharField(max_length=150, blank=True)
    telegram_chat_id = models.BigIntegerField(null=True, blank=True)
    telegram_photo_url = models.URLField(blank=True)

    def __str__(self):
        return self.user.username
