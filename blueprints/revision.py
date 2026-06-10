from flask import Blueprint, render_template, request, redirect, url_for, current_app, g
from auth_utils import login_required
from datetime import datetime, timedelta
from db import GATE_SUBJECTS, add_notification, schedule_revisions

revision_bp = Blueprint('revision', __name__)


@revision_bp.route('/')
@login_required
def index():
    db = current_app.get_db()
    uid = g.current_user['id']
    now = datetime.utcnow()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    today_str = now.date().strftime('%Y-%m-%d')

    overdue = db.execute(
        "SELECT * FROM revisions WHERE user_id=? AND due_date<? AND date(due_date)!=? AND completed=0 ORDER BY due_date",
        (uid, now_str, today_str)
    ).fetchall()

    due_today = db.execute(
        "SELECT * FROM revisions WHERE user_id=? AND date(due_date)=? AND completed=0 ORDER BY due_date",
        (uid, today_str)
    ).fetchall()

    upcoming = db.execute(
        "SELECT * FROM revisions WHERE user_id=? AND due_date>? AND date(due_date)!=? AND completed=0 ORDER BY due_date LIMIT 15",
        (uid, now_str, today_str)
    ).fetchall()

    completed_recent = db.execute(
        "SELECT * FROM revisions WHERE user_id=? AND completed=1 ORDER BY completed_at DESC LIMIT 10",
        (uid,)
    ).fetchall()

    # Stats
    total = db.execute("SELECT COUNT(*) as c FROM revisions WHERE user_id=?", (uid,)).fetchone()['c']
    done = db.execute("SELECT COUNT(*) as c FROM revisions WHERE user_id=? AND completed=1", (uid,)).fetchone()['c']
    rev_pct = round((done / total) * 100) if total else 0

    # Heatmap by subject
    topics = db.execute("SELECT subject, topic, confidence FROM completed_topics WHERE user_id=?", (uid,)).fetchall()
    heatmap = {}
    for t in topics:
        s = t['subject']
        if s not in heatmap:
            heatmap[s] = []
        heatmap[s].append({'topic': t['topic'], 'confidence': t['confidence']})

    return render_template('revision/index.html',
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        completed_recent=completed_recent,
        heatmap=heatmap,
        subjects=GATE_SUBJECTS,
        total=total,
        done=done,
        rev_pct=rev_pct,
        user=g.current_user,
    )


@revision_bp.route('/complete/<int:rev_id>', methods=['POST'])
@login_required
def complete(rev_id):
    db = current_app.get_db()
    uid = g.current_user['id']
    rev = db.execute("SELECT * FROM revisions WHERE id=? AND user_id=?", (rev_id, uid)).fetchone()
    if not rev:
        return redirect(url_for('revision.index'))

    rating = int(request.form.get('rating', 3))
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    db.execute(
        "UPDATE revisions SET completed=1, completed_at=?, confidence_rating=? WHERE id=?",
        (now_str, rating, rev_id)
    )
    if rev['topic_id']:
        db.execute("UPDATE completed_topics SET confidence=? WHERE id=?", (rating, rev['topic_id']))

    # Low confidence -> extra revision in 3 days
    if rating <= 2:
        due = (datetime.utcnow() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            "INSERT INTO revisions (user_id, topic_id, subject, topic, due_date, revision_number) VALUES (?,?,?,?,?,?)",
            (uid, rev['topic_id'], rev['subject'], rev['topic'], due, rev['revision_number'] + 1)
        )
        add_notification(db, uid,
            f"Low confidence on '{rev['topic']}' — extra revision scheduled in 3 days.", 'warning')

    db.commit()
    return redirect(url_for('revision.index'))


@revision_bp.route('/add', methods=['POST'])
@login_required
def add():
    db = current_app.get_db()
    uid = g.current_user['id']
    subject = request.form.get('subject', '')
    topic = request.form.get('topic', '').strip()
    due_days = int(request.form.get('due_days', 1))
    if subject and topic:
        due = (datetime.utcnow() + timedelta(days=due_days)).strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            "INSERT INTO revisions (user_id, subject, topic, due_date) VALUES (?,?,?,?)",
            (uid, subject, topic, due)
        )
        db.commit()
    return redirect(url_for('revision.index'))


@revision_bp.route('/delete/<int:rev_id>', methods=['POST'])
@login_required
def delete(rev_id):
    db = current_app.get_db()
    uid = g.current_user['id']
    db.execute("DELETE FROM revisions WHERE id=? AND user_id=?", (rev_id, uid))
    db.commit()
    return redirect(url_for('revision.index'))
