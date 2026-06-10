from functools import wraps
from flask import session, redirect, url_for, g, current_app


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        # Load current user
        db = current_app.get_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
        if not user:
            session.clear()
            return redirect(url_for('auth.login'))
        g.current_user = user
        return f(*args, **kwargs)
    return decorated
