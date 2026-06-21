from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, current_app, g
from auth_utils import login_required
from datetime import datetime, timedelta
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


@study_bp.route('/manual', methods=['GET', 'POST'])
@login_required
def manual():
    db = current_app.get_db()
    uid = g.current_user['id']

    if request.method == 'POST':
        subject = request.form.get('subject', '')
        topic = request.form.get('topic', '').strip()
        stype = request.form.get('session_type', 'Learning')
        date_str = request.form.get('date', '')
        hours = request.form.get('hours', '0').strip()
        minutes = request.form.get('minutes', '0').strip()
        notes = request.form.get('notes', '').strip()
        mark_complete = request.form.get('mark_topic_complete') == 'on'
        confidence = int(request.form.get('confidence', 3))

        errors = []
        if not subject:
            errors.append('Please select a subject.')
        if not date_str:
            errors.append('Please pick a date.')

        try:
            h = int(hours) if hours else 0
        except ValueError:
            h = 0
        try:
            m = int(minutes) if minutes else 0
        except ValueError:
            m = 0
        duration = h * 60 + m

        if duration <= 0:
            errors.append('Enter a study duration greater than 0.')

        try:
            entry_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            entry_date = None
            errors.append('Invalid date.')

        if errors:
            return render_template('study/manual.html',
                subjects=GATE_SUBJECTS,
                session_types=SESSION_TYPES,
                user=g.current_user,
                errors=errors,
                form=request.form,
            )

        # Anchor the stored timestamps to the chosen date so streaks/analytics
        # (which group by date(started_at)) line up correctly, but keep a
        # plausible end time = start + duration.
        started_at = entry_date.replace(hour=20, minute=0, second=0)
        ended_at = started_at + timedelta(minutes=duration)

        cur = db.execute(
            "INSERT INTO study_sessions (user_id, subject, topic, session_type, started_at, ended_at, duration_minutes, notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (uid, subject, topic, stype,
             started_at.strftime('%Y-%m-%d %H:%M:%S'),
             ended_at.strftime('%Y-%m-%d %H:%M:%S'),
             duration, notes)
        )
        db.commit()

        if mark_complete and topic:
            tcur = db.execute(
                "INSERT INTO completed_topics (user_id, subject, topic, confidence) VALUES (?,?,?,?)",
                (uid, subject, topic, confidence)
            )
            db.commit()
            topic_id = tcur.lastrowid
            schedule_revisions(db, uid, topic_id, subject, topic)
            add_notification(db, uid,
                f"Topic '{topic}' marked complete! Revisions scheduled for Day 3, 7 & 30.", 'success')

        return redirect(url_for('study.manual', saved=1))

    recent = db.execute(
        "SELECT * FROM study_sessions WHERE user_id=? AND duration_minutes IS NOT NULL ORDER BY started_at DESC LIMIT 10",
        (uid,)
    ).fetchall()

    return render_template('study/manual.html',
        subjects=GATE_SUBJECTS,
        session_types=SESSION_TYPES,
        user=g.current_user,
        recent=recent,
        saved=request.args.get('saved'),
        today=datetime.utcnow().strftime('%Y-%m-%d'),
    )


@study_bp.route('/api/ping/<int:session_id>', methods=['POST'])
@login_required
def ping(session_id):
    db = current_app.get_db()
    uid = g.current_user['id']
    sess = db.execute("SELECT * FROM study_sessions WHERE id=? AND user_id=?", (session_id, uid)).fetchone()
    if sess and not sess['ended_at']:
        return jsonify({'status': 'active', 'started': sess['started_at']})
    return jsonify({'status': 'not_found'}), 404