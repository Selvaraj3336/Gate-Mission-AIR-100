from flask import Blueprint, render_template, request, redirect, url_for, current_app, g, flash
from auth_utils import login_required
from db import GATE_SUBJECTS, get_streak, get_longest_streak, get_today_hours, get_weekly_hours

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/')
@login_required
def index():
    db = current_app.get_db()
    uid = g.current_user['id']
    user = g.current_user

    streak = get_streak(db, uid)
    longest = get_longest_streak(db, uid)
    today_hrs = get_today_hours(db, uid)
    weekly_hrs = get_weekly_hours(db, uid)

    total_sessions = db.execute("SELECT COUNT(*) as c FROM study_sessions WHERE user_id=? AND ended_at IS NOT NULL", (uid,)).fetchone()['c']
    total_topics = db.execute("SELECT COUNT(*) as c FROM completed_topics WHERE user_id=?", (uid,)).fetchone()['c']
    total_revisions = db.execute("SELECT COUNT(*) as c FROM revisions WHERE user_id=? AND completed=1", (uid,)).fetchone()['c']
    total_mocks = db.execute("SELECT COUNT(*) as c FROM mock_tests WHERE user_id=?", (uid,)).fetchone()['c']
    total_hrs_row = db.execute("SELECT COALESCE(SUM(duration_minutes),0) as t FROM study_sessions WHERE user_id=? AND ended_at IS NOT NULL", (uid,)).fetchone()
    total_hours = round((total_hrs_row['t'] or 0) / 60, 1)

    # Notifications
    notifications = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (uid,)).fetchall()
    unread_count = db.execute("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND read=0", (uid,)).fetchone()['c']

    return render_template('profile/index.html',
        user=user,
        streak=streak,
        longest=longest,
        today_hrs=today_hrs,
        weekly_hrs=weekly_hrs,
        total_sessions=total_sessions,
        total_topics=total_topics,
        total_revisions=total_revisions,
        total_mocks=total_mocks,
        total_hours=total_hours,
        notifications=notifications,
        unread_count=unread_count,
        subjects=GATE_SUBJECTS,
    )


@profile_bp.route('/update', methods=['POST'])
@login_required
def update():
    db = current_app.get_db()
    uid = g.current_user['id']
    daily_hours = float(request.form.get('daily_goal_hours', 5.0))
    daily_pyqs = int(request.form.get('daily_goal_pyqs', 30))
    weekly_hours = float(request.form.get('weekly_goal_hours', 30.0))
    db.execute(
        "UPDATE users SET daily_goal_hours=?, daily_goal_pyqs=?, weekly_goal_hours=? WHERE id=?",
        (daily_hours, daily_pyqs, weekly_hours, uid)
    )
    db.commit()
    flash('Goals updated successfully! 🎯', 'success')
    return redirect(url_for('profile.index'))


@profile_bp.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    db = current_app.get_db()
    uid = g.current_user['id']
    db.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))
    db.commit()
    return redirect(url_for('profile.index'))
