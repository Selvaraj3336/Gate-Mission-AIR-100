from flask import Blueprint, render_template, current_app, g, jsonify
from auth_utils import login_required
from datetime import datetime, timedelta
from db import get_streak, get_today_hours, get_weekly_hours, get_air_estimate, get_unread_notifications, GATE_DATE, GATE_SUBJECTS

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    db = current_app.get_db()
    user = g.current_user
    uid = user['id']
    today = datetime.utcnow().date()

    days_left = (GATE_DATE.date() - today).days
    streak = get_streak(db, uid)
    today_hours = get_today_hours(db, uid)
    weekly_hours_total = get_weekly_hours(db, uid)
    air_data = get_air_estimate(db, uid)
    notifications = get_unread_notifications(db, uid)

    # Today's due revisions
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    today_str = today.strftime('%Y-%m-%d')

    due_today = db.execute(
        "SELECT * FROM revisions WHERE user_id=? AND date(due_date)=? AND completed=0 ORDER BY due_date",
        (uid, today_str)
    ).fetchall()

    overdue = db.execute(
        "SELECT * FROM revisions WHERE user_id=? AND due_date<? AND date(due_date)!=? AND completed=0 ORDER BY due_date",
        (uid, now_str, today_str)
    ).fetchall()

    upcoming = db.execute(
        "SELECT * FROM revisions WHERE user_id=? AND due_date>? AND date(due_date)!=? AND completed=0 ORDER BY due_date LIMIT 5",
        (uid, now_str, today_str)
    ).fetchall()

    # Recent mock tests
    recent_mocks = db.execute(
        "SELECT * FROM mock_tests WHERE user_id=? ORDER BY date DESC LIMIT 3",
        (uid,)
    ).fetchall()

    # Weekly sparkline (last 7 days)
    weekly_data = []
    weekly_labels = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        row = db.execute(
            "SELECT COALESCE(SUM(duration_minutes),0) as t FROM study_sessions WHERE user_id=? AND date(started_at)=? AND ended_at IS NOT NULL",
            (uid, day.strftime('%Y-%m-%d'))
        ).fetchone()
        weekly_data.append(round((row['t'] or 0) / 60, 1))
        weekly_labels.append(day.strftime('%a'))

    goal_hours = user['daily_goal_hours'] or 5.0
    goal_pct = min(100, round((today_hours / goal_hours) * 100)) if goal_hours else 0

    # Total topics completed
    total_topics = db.execute("SELECT COUNT(*) as c FROM completed_topics WHERE user_id=?", (uid,)).fetchone()['c']

    return render_template('dashboard/index.html',
        days_left=days_left,
        streak=streak,
        today_hours=today_hours,
        weekly_hours_total=weekly_hours_total,
        goal_hours=goal_hours,
        goal_pct=goal_pct,
        air_data=air_data,
        due_today=due_today,
        overdue=overdue,
        upcoming=upcoming,
        recent_mocks=recent_mocks,
        weekly_data=weekly_data,
        weekly_labels=weekly_labels,
        total_topics=total_topics,
        notifications=notifications,
        subjects=GATE_SUBJECTS,
        user=user,
    )


@dashboard_bp.route('/api/stats')
@login_required
def api_stats():
    db = current_app.get_db()
    uid = g.current_user['id']
    return jsonify({
        'today_hours': get_today_hours(db, uid),
        'streak': get_streak(db, uid),
        'air': get_air_estimate(db, uid)
    })
