from django.urls import path

from . import views


urlpatterns = [
    path("events/", views.event_list, name="event_list"),
    path("events/new/", views.event_create, name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/edit/", views.event_update, name="event_update"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("reminders/new/", views.reminder_create, name="reminder_create"),
    path("reminders/<int:pk>/done/", views.reminder_done, name="reminder_done"),
]
