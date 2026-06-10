from flask import Blueprint, render_template, redirect, url_for, request, current_app, g
from auth_utils import login_required
from datetime import datetime, timedelta
from db import GATE_SUBJECTS, get_air_estimate

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/')
@login_required
def index():
    db = current_app.get_db()
    uid = g.current_user['id']
    today = datetime.utcnow().date()

    # Daily hours - last 14 days
    daily_hours = []
    daily_labels = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        row = db.execute(
            "SELECT COALESCE(SUM(duration_minutes),0) as t FROM study_sessions WHERE user_id=? AND date(started_at)=? AND ended_at IS NOT NULL",
            (uid, day.strftime('%Y-%m-%d'))
        ).fetchone()
        daily_hours.append(round((row['t'] or 0) / 60, 1))
        daily_labels.append(day.strftime('%d %b'))

    # Subject-wise hours sorted in Python
    rows = db.execute(
        "SELECT subject, COALESCE(SUM(duration_minutes),0) as t FROM study_sessions WHERE user_id=? AND ended_at IS NOT NULL GROUP BY subject ORDER BY t DESC",
        (uid,)
    ).fetchall()
    subject_hours_list = [
        {'subject': r['subject'], 'hrs': round(r['t'] / 60, 1)}
        for r in rows
    ]
    max_hrs = max((r['hrs'] for r in subject_hours_list), default=1) or 1

    # Mock tests
    mocks = db.execute("SELECT * FROM mock_tests WHERE user_id=? ORDER BY date", (uid,)).fetchall()
    mock_labels = [m['date'][:10] for m in mocks]
    mock_scores = [float(m['marks']) for m in mocks]

    # PYQ
    raw_pyq = db.execute("SELECT * FROM pyq_progress WHERE user_id=? ORDER BY subject", (uid,)).fetchall()
    pyq_data = []
    for p in raw_pyq:
        solved  = p['solved']  or 0
        correct = p['correct'] or 0
        wrong   = p['wrong']   or 0
        acc     = round((correct / solved) * 100, 1) if solved else 0
        pyq_data.append({
            'subject':  p['subject'],
            'solved':   solved,
            'correct':  correct,
            'wrong':    wrong,
            'accuracy': acc,
        })

    # Error notebook
    errors = db.execute(
        "SELECT * FROM error_notebook WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (uid,)
    ).fetchall()

    # AIR estimate
    try:
        air = get_air_estimate(db, uid)
    except Exception:
        air = {'probability': 0, 'estimated_air': 9999, 'on_track': False}

    # Revision completion
    total_rev = db.execute("SELECT COUNT(*) as c FROM revisions WHERE user_id=?", (uid,)).fetchone()['c']
    done_rev  = db.execute("SELECT COUNT(*) as c FROM revisions WHERE user_id=? AND completed=1", (uid,)).fetchone()['c']
    rev_pct   = round((done_rev / total_rev) * 100) if total_rev else 0

    # Total study hours
    total_hrs_row = db.execute(
        "SELECT COALESCE(SUM(duration_minutes),0) as t FROM study_sessions WHERE user_id=? AND ended_at IS NOT NULL",
        (uid,)
    ).fetchone()
    total_hours = round((total_hrs_row['t'] or 0) / 60, 1)

    session_count = db.execute(
        "SELECT COUNT(*) as c FROM study_sessions WHERE user_id=? AND ended_at IS NOT NULL", (uid,)
    ).fetchone()['c']

    return render_template('analytics/index.html',
        daily_labels=daily_labels,
        daily_hours=daily_hours,
        subject_hours_list=subject_hours_list,
        max_hrs=max_hrs,
        mock_labels=mock_labels,
        mock_scores=mock_scores,
        mocks=mocks,
        pyq_data=pyq_data,
        errors=errors,
        air=air,
        subjects=GATE_SUBJECTS,
        rev_pct=rev_pct,
        total_rev=total_rev,
        done_rev=done_rev,
        total_hours=total_hours,
        session_count=session_count,
        user=g.current_user,
    )


@analytics_bp.route('/error/add', methods=['POST'])
@login_required
def add_error():
    db = current_app.get_db()
    uid = g.current_user['id']
    db.execute(
        "INSERT INTO error_notebook (user_id, subject, topic, question, mistake, correction) VALUES (?,?,?,?,?,?)",
        (uid,
         request.form.get('subject', ''),
         request.form.get('topic', ''),
         request.form.get('question', ''),
         request.form.get('mistake', ''),
         request.form.get('correction', ''))
    )
    db.commit()
    return redirect(url_for('analytics.index'))