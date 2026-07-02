# Planly

Planly is a shared calendar app for personal plans and future group plans with friends.

This is a Django portfolio project. The first version is intentionally simple: user accounts and private events. Friend requests, invitations, and Telegram Mini App integration will be added after the base app works well.

## Current Features

- user registration;
- login and logout;
- create private plans;
- create private reminders;
- view upcoming plans;
- mark reminders as done;
- view plan details;
- edit own plans;
- delete own plans;
- mobile-first UI.

## Tech Stack

- Python;
- Django;
- SQLite for local development;
- Django templates;
- CSS.

## Run Locally

Install dependencies:

```bash
uv sync
```

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

## Roadmap

- friend requests;
- event invitations;
- accepted and declined invitation statuses;
- shared events;
- real reminder notifications;
- simple notification page;
- PostgreSQL;
- Telegram Mini App authentication.
