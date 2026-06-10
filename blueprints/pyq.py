from flask import Blueprint, render_template, request, redirect, url_for, current_app, g
from auth_utils import login_required
from datetime import datetime
from db import GATE_SUBJECTS

pyq_bp = Blueprint('pyq', __name__)


@pyq_bp.route('/')
@login_required
def index():
    db = current_app.get_db()
    uid = g.current_user['id']

    pyq_rows = db.execute("SELECT * FROM pyq_progress WHERE user_id=? ORDER BY subject", (uid,)).fetchall()

    # Build subject dict with defaults
    pyq_map = {r['subject']: dict(r) for r in pyq_rows}
    pyq_data = []
    total_solved = total_correct = total_wrong = 0

    for subj in GATE_SUBJECTS:
        d = pyq_map.get(subj, {'subject': subj, 'solved': 0, 'correct': 0, 'wrong': 0})
        solved = d.get('solved', 0) or 0
        correct = d.get('correct', 0) or 0
        wrong = d.get('wrong', 0) or 0
        acc = round((correct / solved) * 100, 1) if solved else 0
        pyq_data.append({
            'subject': subj,
            'solved': solved,
            'correct': correct,
            'wrong': wrong,
            'accuracy': acc,
        })
        total_solved += solved
        total_correct += correct
        total_wrong += wrong

    overall_acc = round((total_correct / total_solved) * 100, 1) if total_solved else 0

    return render_template('pyq/index.html',
        pyq_data=pyq_data,
        subjects=GATE_SUBJECTS,
        total_solved=total_solved,
        total_correct=total_correct,
        total_wrong=total_wrong,
        overall_acc=overall_acc,
        user=g.current_user,
    )


@pyq_bp.route('/update', methods=['POST'])
@login_required
def update():
    db = current_app.get_db()
    uid = g.current_user['id']
    subject = request.form.get('subject', '')
    solved = int(request.form.get('solved', 0))
    correct = int(request.form.get('correct', 0))
    wrong = int(request.form.get('wrong', 0))
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    existing = db.execute("SELECT id FROM pyq_progress WHERE user_id=? AND subject=?", (uid, subject)).fetchone()
    if existing:
        db.execute(
            "UPDATE pyq_progress SET solved=solved+?, correct=correct+?, wrong=wrong+?, updated_at=? WHERE user_id=? AND subject=?",
            (solved, correct, wrong, now, uid, subject)
        )
    else:
        db.execute(
            "INSERT INTO pyq_progress (user_id, subject, solved, correct, wrong, updated_at) VALUES (?,?,?,?,?,?)",
            (uid, subject, solved, correct, wrong, now)
        )
    db.commit()
    return redirect(url_for('pyq.index'))


@pyq_bp.route('/reset/<subject>', methods=['POST'])
@login_required
def reset(subject):
    db = current_app.get_db()
    uid = g.current_user['id']
    db.execute("DELETE FROM pyq_progress WHERE user_id=? AND subject=?", (uid, subject))
    db.commit()
    return redirect(url_for('pyq.index'))
