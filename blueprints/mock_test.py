from flask import Blueprint, render_template, request, redirect, url_for, current_app, g
from auth_utils import login_required
from datetime import datetime
from db import GATE_SUBJECTS

mock_bp = Blueprint('mock', __name__)


@mock_bp.route('/')
@login_required
def index():
    db = current_app.get_db()
    uid = g.current_user['id']

    mocks = db.execute("SELECT * FROM mock_tests WHERE user_id=? ORDER BY date DESC", (uid,)).fetchall()

    # Stats
    if mocks:
        avg_score = sum(m['marks'] / (m['max_marks'] or 100) * 100 for m in mocks) / len(mocks)
        best = max(mocks, key=lambda m: m['marks'] / (m['max_marks'] or 100) * 100)
        best_pct = round(best['marks'] / (best['max_marks'] or 100) * 100, 1)
        latest_pct = round(mocks[0]['marks'] / (mocks[0]['max_marks'] or 100) * 100, 1)
        trend = 'up' if len(mocks) >= 2 and mocks[0]['marks'] >= mocks[1]['marks'] else 'down'
    else:
        avg_score = best_pct = latest_pct = 0
        trend = 'neutral'
        best = None

    # Error type totals
    total_concept = sum(m['concept_errors'] or 0 for m in mocks)
    total_silly = sum(m['silly_mistakes'] or 0 for m in mocks)
    total_time = sum(m['time_errors'] or 0 for m in mocks)
    total_guess = sum(m['guess_errors'] or 0 for m in mocks)

    # Chart data
    chart_labels = [m['date'][:10] for m in reversed(list(mocks))]
    chart_scores = [round(m['marks'] / (m['max_marks'] or 100) * 100, 1) for m in reversed(list(mocks))]

    return render_template('mock_test/index.html',
        mocks=mocks,
        avg_score=round(avg_score, 1),
        best_pct=best_pct,
        latest_pct=latest_pct,
        trend=trend,
        total_concept=total_concept,
        total_silly=total_silly,
        total_time=total_time,
        total_guess=total_guess,
        chart_labels=chart_labels,
        chart_scores=chart_scores,
        subjects=GATE_SUBJECTS,
        user=g.current_user,
    )


@mock_bp.route('/add', methods=['POST'])
@login_required
def add():
    db = current_app.get_db()
    uid = g.current_user['id']
    name = request.form.get('test_name', 'Mock Test').strip()
    marks = float(request.form.get('marks', 0))
    max_marks = float(request.form.get('max_marks', 100))
    accuracy = float(request.form.get('accuracy', 0)) if request.form.get('accuracy') else None
    concept = int(request.form.get('concept_errors', 0))
    silly = int(request.form.get('silly_mistakes', 0))
    time_err = int(request.form.get('time_errors', 0))
    guess_err = int(request.form.get('guess_errors', 0))
    notes = request.form.get('notes', '')
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    db.execute(
        "INSERT INTO mock_tests (user_id, test_name, date, marks, max_marks, accuracy, concept_errors, silly_mistakes, time_errors, guess_errors, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (uid, name, now, marks, max_marks, accuracy, concept, silly, time_err, guess_err, notes)
    )
    db.commit()
    return redirect(url_for('mock.index'))


@mock_bp.route('/delete/<int:mid>', methods=['POST'])
@login_required
def delete(mid):
    db = current_app.get_db()
    uid = g.current_user['id']
    db.execute("DELETE FROM mock_tests WHERE id=? AND user_id=?", (mid, uid))
    db.commit()
    return redirect(url_for('mock.index'))
