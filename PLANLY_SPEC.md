# Planly Spec

Planly is a shared calendar app for personal plans, friend plans, and group invitations.

The goal is to build a simple but useful Django project that can later become a Telegram Mini App.

## Main Idea

A user can use Planly as a normal calendar:

- create private events;
- create events visible to friends;
- invite friends to group plans;
- accept or decline invitations;
- see upcoming plans in one place.

## MVP v1

The first version should stay small and finished.

### Accounts

- register;
- login;
- logout;
- profile page later, not required at first.

### Events

Each event has:

- owner;
- title;
- description;
- start date and time;
- end date and time;
- location;
- visibility;
- created date;
- updated date.

Visibility options:

- private;
- friends;
- invite_only.

### Friends

Users can:

- send friend requests;
- accept friend requests;
- decline friend requests;
- see their friends list.

### Invitations

Event owner can:

- choose friends for an event;
- send invitations.

Invited user can:

- see pending invitations;
- accept invitation;
- decline invitation.

Invitation statuses:

- pending;
- accepted;
- declined.

### Dashboard

The dashboard should show:

- upcoming own events;
- shared events;
- pending invitations.

## MVP v2

Add after v1 works:

- event change proposals;
- comments under events;
- notification page;
- simple month calendar view;
- PostgreSQL;
- Telegram Mini App authentication;
- deployment.

## Not In First Version

Do not add these at the start:

- React;
- Celery;
- Redis;
- Docker;
- Google Calendar sync;
- push notifications;
- recurring events;
- complex timezone logic;
- chat.

## Django Apps

Project structure:

```text
planly/
├── config/
├── accounts/
├── planner/
├── templates/
├── static/
├── manage.py
├── pyproject.toml
└── README.md
```

Apps:

- accounts;
- planner.

## Models

Use Django default User model at first.

### Event

Fields:

- owner;
- title;
- description;
- start_at;
- end_at;
- location;
- visibility;
- created_at;
- updated_at.

### FriendRequest

Fields:

- from_user;
- to_user;
- status;
- created_at;
- updated_at.

Statuses:

- pending;
- accepted;
- declined.

### EventInvitation

Fields:

- event;
- user;
- status;
- created_at;
- updated_at.

Statuses:

- pending;
- accepted;
- declined.

## Access Rules

A user can see an event if:

- they own the event;
- the event is visible to friends and the user is a friend of the owner;
- the user was invited to the event.

A user can edit or delete an event only if they own it.

A user can accept or decline only their own invitation.

## Pages

First version pages:

```text
/register/
/login/
/logout/

/events/
/events/new/
/events/<id>/
/events/<id>/edit/
/events/<id>/delete/

/friends/
/friends/find/
/invitations/
```

## UI Direction

The interface should be:

- mobile-first;
- simple;
- clean;
- comfortable inside Telegram Mini App later.

Use:

- cards;
- bottom navigation later;
- large buttons;
- readable spacing;
- simple colors.

## Code Style

Keep code simple:

- function-based views;
- Django forms;
- Django templates;
- simple model methods only when needed;
- no unnecessary architecture layers;
- clear variable names;
- comments only when they explain non-obvious logic.

The code should be easy to explain in an interview.

## Portfolio Goal

Planly should show:

- Django models;
- relationships between users and events;
- authentication;
- permissions;
- event invitations;
- status logic;
- basic tests;
- mobile-first UI;
- readiness for Telegram Mini App integration.

