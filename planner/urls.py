from django.urls import path

from . import views


urlpatterns = [
    path("events/", views.event_list, name="event_list"),
    path("events/new/", views.event_create, name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/edit/", views.event_update, name="event_update"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path(
        "events/invites/<int:pk>/accept/",
        views.event_invite_accept,
        name="event_invite_accept",
    ),
    path(
        "events/invites/<int:pk>/decline/",
        views.event_invite_decline,
        name="event_invite_decline",
    ),
    path("reminders/new/", views.reminder_create, name="reminder_create"),
    path("reminders/<int:pk>/", views.reminder_detail, name="reminder_detail"),
    path("reminders/<int:pk>/edit/", views.reminder_update, name="reminder_update"),
    path("reminders/<int:pk>/delete/", views.reminder_delete, name="reminder_delete"),
    path("reminders/<int:pk>/done/", views.reminder_done, name="reminder_done"),
    path("friends/", views.friends, name="friends"),
    path("friends/add/", views.friend_request_create, name="friend_request_create"),
    path(
        "friends/requests/<int:pk>/accept/",
        views.friend_request_accept,
        name="friend_request_accept",
    ),
    path(
        "friends/requests/<int:pk>/reject/",
        views.friend_request_reject,
        name="friend_request_reject",
    ),
]
