# GATE Mission AIR-100

A complete mobile-first web application for GATE CS preparation targeting AIR < 100.

## Features
- User Authentication (register/login/logout)
- Dashboard with AIR prediction, streak, countdown, study hours
- Study Session System with full-screen focus mode & live timer
- Revision Intelligence (spaced repetition: Day 3, 7, 30)
- Study Analytics with charts
- Mock Test Tracker with error analysis
- PYQ Tracker (subject-wise accuracy)
- Streak System (current & longest)
- Notifications for revisions & topic completion
- Mobile-first responsive dark UI

## Setup & Run

### Requirements
- Python 3.10+
- Flask (only dependency!)

### Install
```bash
pip install flask werkzeug
```

### Run
```bash
python app.py
# or
./run.sh
```

Open http://localhost:5000 in your browser.

## Architecture
- `app.py` — Flask application factory
- `db.py` — SQLite schema, helpers, business logic
- `auth_utils.py` — Session-based login_required decorator
- `blueprints/` — Route handlers (auth, dashboard, study, revision, analytics, mock_test, pyq, profile)
- `templates/` — Jinja2 HTML templates (mobile-first dark UI)
- `gate_mission.db` — SQLite database (auto-created on first run)

## No external dependencies needed
Uses only Flask + Python stdlib sqlite3 — no Flask-SQLAlchemy, no Flask-Login needed.
