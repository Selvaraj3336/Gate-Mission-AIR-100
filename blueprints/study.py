from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, current_app, g
from auth_utils import login_required
from datetime import datetime
from db import GATE_SUBJECTS, SESSION_TYPES, schedule_revisions, add_notification, get_today_hours

study_bp = Blueprint('study', __name__)


@study_bp.route('/')
@login_required
def index():
    db = current_app.get_db()
    uid = g.current_user['id']
    active = None
    if 'active_session_id' in session:
        row = db.execute("SELECT * FROM study_sessions WHERE id=? AND user_id=?",
                         (session['active_session_id'], uid)).fetchone()
        if row and not row['ended_at']:
            active = row
        else:
            session.pop('active_session_id', None)

    # Recent sessions
    recent = db.execute(
        "SELECT * FROM study_sessions WHERE user_id=? AND ended_at IS NOT NULL ORDER BY started_at DESC LIMIT 10",
        (uid,)
    ).fetchall()

    return render_template('study/index.html',
        subjects=GATE_SUBJECTS,
        session_types=SESSION_TYPES,
        active_session=active,
        recent=recent,
        user=g.current_user,
    )


@study_bp.route('/start', methods=['POST'])
@login_required
def start():
    db = current_app.get_db()
    uid = g.current_user['id']
    subject = request.form.get('subject', '')
    topic = request.form.get('topic', '').strip()
    stype = request.form.get('session_type', 'Learning')
    if not subject:
        return redirect(url_for('study.index'))
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cur = db.execute(
        "INSERT INTO study_sessions (user_id, subject, topic, session_type, started_at) VALUES (?,?,?,?,?)",
        (uid, subject, topic, stype, now)
    )
    db.commit()
    sid = cur.lastrowid
    session['active_session_id'] = sid
    return redirect(url_for('study.focus', session_id=sid))


@study_bp.route('/focus/<int:session_id>')
@login_required
def focus(session_id):
    db = current_app.get_db()
    uid = g.current_user['id']
    sess = db.execute("SELECT * FROM study_sessions WHERE id=? AND user_id=?", (session_id, uid)).fetchone()
    if not sess:
        return redirect(url_for('study.index'))
    user = g.current_user
    today_hours = get_today_hours(db, uid)
    return render_template('study/focus.html',
        study_session=sess,
        goal_hours=user['daily_goal_hours'] or 5.0,
        today_hours=today_hours,
        user=user,
    )


@study_bp.route('/end/<int:session_id>', methods=['POST'])
@login_required
def end(session_id):
    db = current_app.get_db()
    uid = g.current_user['id']
    sess = db.execute("SELECT * FROM study_sessions WHERE id=? AND user_id=?", (session_id, uid)).fetchone()
    if not sess:
        return redirect(url_for('study.index'))

    notes = request.form.get('notes', '')
    mark_complete = request.form.get('mark_topic_complete') == 'on'
    confidence = int(request.form.get('confidence', 3))

    now = datetime.utcnow()
    started = datetime.strptime(sess['started_at'], '%Y-%m-%d %H:%M:%S')
    duration = max(1, int((now - started).total_seconds() / 60))

    db.execute(
        "UPDATE study_sessions SET ended_at=?, duration_minutes=?, notes=? WHERE id=?",
        (now.strftime('%Y-%m-%d %H:%M:%S'), duration, notes, session_id)
    )
    db.commit()

    if mark_complete and sess['topic']:
        cur = db.execute(
            "INSERT INTO completed_topics (user_id, subject, topic, confidence) VALUES (?,?,?,?)",
            (uid, sess['subject'], sess['topic'], confidence)
        )
        db.commit()
        topic_id = cur.lastrowid
        schedule_revisions(db, uid, topic_id, sess['subject'], sess['topic'])
        add_notification(db, uid,
            f"Topic '{sess['topic']}' marked complete! Revisions scheduled for Day 3, 7 & 30.", 'success')

    session.pop('active_session_id', None)
    return redirect(url_for('dashboard.index'))


@study_bp.route('/api/ping/<int:session_id>', methods=['POST'])
@login_required
def ping(session_id):
    db = current_app.get_db()
    uid = g.current_user['id']
    sess = db.execute("SELECT * FROM study_sessions WHERE id=? AND user_id=?", (session_id, uid)).fetchone()
    if sess and not sess['ended_at']:
        return jsonify({'status': 'active', 'started': sess['started_at']})
    return jsonify({'status': 'not_found'}), 404
