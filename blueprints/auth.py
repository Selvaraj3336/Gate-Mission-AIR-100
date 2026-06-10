from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')
        db = current_app.get_db()
        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')
        pw = generate_password_hash(password)
        cur = db.execute("INSERT INTO users (name, email, password_hash) VALUES (?,?,?)", (name, email, pw))
        db.commit()
        session['user_id'] = cur.lastrowid
        session['user_name'] = name
        flash(f'Welcome, {name}! Your GATE mission begins now 🚀', 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        db = current_app.get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session.permanent = True
            return redirect(url_for('dashboard.index'))
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
