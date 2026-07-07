# Planly

Planly is a shared calendar app for personal plans, reminders, and group plans with friends.

This is a Django portfolio project. The current version is a small MVP: users can create plans, manage private reminders, add friends, and invite friends to shared events.

Status: in progress.

## Current Features

- user registration;
- login and logout;
- create, view, edit, and delete own events;
- create private reminders;
- edit and delete own reminders;
- mark reminders as done;
- send friend requests by username;
- accept or reject friend requests;
- invite accepted friends to events;
- accept or decline event invitations;
- view own events, shared events, pending invitations, and reminders;
- user-level access control: users can only open their own events or accepted shared events;
- mobile-first UI.

## Tech Stack

- Python;
- Django;
- Django Auth;
- Django ORM;
- SQLite for local development;
- Django templates;
- CSS;
- pytest / Django test runner.

## Run Locally

Install dependencies:

```bash
uv sync
```

Create a local environment file:

```bash
cp .env.example .env
```

Add your local Django secret key to `.env`.

Apply migrations:

```bash
uv run python manage.py migrate
```

Start the server:

```bash
uv run python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Run tests:

```bash
uv run python manage.py test
```

## Roadmap

- improve the calendar/dashboard view;
- add user profiles;
- real reminder notifications;
- simple notification page;
- PostgreSQL;
- deploy the app;
- Telegram Mini App authentication.
