import sqlite3
from datetime import datetime, timedelta


GATE_SUBJECTS = [
    'Engineering Mathematics',
    'Discrete Mathematics',
    'Digital Logic',
    'Computer Organization & Architecture',
    'Programming & Data Structures',
    'Algorithms',
    'Theory of Computation',
    'Compiler Design',
    'Operating Systems',
    'Databases',
    'Computer Networks',
    'General Aptitude',
]

SESSION_TYPES = ['Learning', 'Revision', 'PYQ Practice', 'Mock Test', 'Notes Reading']

GATE_DATE = datetime(2027, 2, 1)


def init_db(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            daily_goal_hours REAL DEFAULT 5.0,
            daily_goal_pyqs INTEGER DEFAULT 30,
            weekly_goal_hours REAL DEFAULT 30.0,
            gate_target_air INTEGER DEFAULT 100
        );

        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subject TEXT NOT NULL,
            topic TEXT,
            session_type TEXT DEFAULT 'Learning',
            started_at TEXT DEFAULT (datetime('now')),
            ended_at TEXT,
            duration_minutes INTEGER,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS completed_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            completed_at TEXT DEFAULT (datetime('now')),
            confidence INTEGER DEFAULT 3
        );

        CREATE TABLE IF NOT EXISTS revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            topic_id INTEGER REFERENCES completed_topics(id),
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            confidence_rating INTEGER,
            revision_number INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS mock_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            test_name TEXT DEFAULT 'Mock Test',
            date TEXT DEFAULT (datetime('now')),
            marks REAL NOT NULL,
            max_marks REAL DEFAULT 100,
            accuracy REAL,
            concept_errors INTEGER DEFAULT 0,
            silly_mistakes INTEGER DEFAULT 0,
            time_errors INTEGER DEFAULT 0,
            guess_errors INTEGER DEFAULT 0,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS pyq_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subject TEXT NOT NULL,
            year INTEGER DEFAULT 0,
            solved INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            wrong INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, subject)
        );

        CREATE TABLE IF NOT EXISTS error_notebook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subject TEXT NOT NULL,
            topic TEXT,
            question TEXT NOT NULL,
            mistake TEXT,
            correction TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    ''')
    db.commit()


def schedule_revisions(db, user_id, topic_id, subject, topic):
    intervals = [3, 7, 30]
    for i, days in enumerate(intervals):
        due = (datetime.utcnow() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            'INSERT INTO revisions (user_id, topic_id, subject, topic, due_date, revision_number) VALUES (?,?,?,?,?,?)',
            (user_id, topic_id, subject, topic, due, i + 1)
        )
    db.commit()


def get_streak(db, user_id):
    today = datetime.utcnow().date()
    streak = 0
    check = today
    while True:
        row = db.execute(
            "SELECT 1 FROM study_sessions WHERE user_id=? AND date(started_at)=? AND ended_at IS NOT NULL LIMIT 1",
            (user_id, check.strftime('%Y-%m-%d'))
        ).fetchone()
        if row:
            streak += 1
            check -= timedelta(days=1)
        else:
            break
    return streak


def get_longest_streak(db, user_id):
    rows = db.execute(
        "SELECT DISTINCT date(started_at) as d FROM study_sessions WHERE user_id=? AND ended_at IS NOT NULL ORDER BY d",
        (user_id,)
    ).fetchall()
    if not rows:
        return 0
    from datetime import date
    dates = [datetime.strptime(r['d'], '%Y-%m-%d').date() for r in rows]
    longest = 1
    current = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i-1]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def get_today_hours(db, user_id):
    today = datetime.utcnow().date().strftime('%Y-%m-%d')
    row = db.execute(
        "SELECT COALESCE(SUM(duration_minutes),0) as total FROM study_sessions WHERE user_id=? AND date(started_at)=? AND ended_at IS NOT NULL",
        (user_id, today)
    ).fetchone()
    return round((row['total'] or 0) / 60, 1)


def get_weekly_hours(db, user_id):
    since = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    row = db.execute(
        "SELECT COALESCE(SUM(duration_minutes),0) as total FROM study_sessions WHERE user_id=? AND started_at>=? AND ended_at IS NOT NULL",
        (user_id, since)
    ).fetchone()
    return round((row['total'] or 0) / 60, 1)


def get_air_estimate(db, user_id):
    score = 0
    weekly_hrs = get_weekly_hours(db, user_id)
    score += min(30, weekly_hrs * 2)

    total_rev = db.execute("SELECT COUNT(*) as c FROM revisions WHERE user_id=?", (user_id,)).fetchone()['c']
    done_rev = db.execute("SELECT COUNT(*) as c FROM revisions WHERE user_id=? AND completed=1", (user_id,)).fetchone()['c']
    if total_rev:
        score += 25 * (done_rev / total_rev)

    mocks = db.execute("SELECT marks, max_marks FROM mock_tests WHERE user_id=? ORDER BY date DESC LIMIT 5", (user_id,)).fetchall()
    if mocks:
        avg = sum(m['marks'] / (m['max_marks'] or 100) * 100 for m in mocks) / len(mocks)
        score += 25 * (avg / 100)

    streak = get_streak(db, user_id)
    score += min(20, streak * 0.5)

    prob = min(95, score)
    if prob >= 80:
        est_air = 50
    elif prob >= 65:
        est_air = 200
    elif prob >= 50:
        est_air = 500
    elif prob >= 35:
        est_air = 1500
    else:
        est_air = 5000

    return {'probability': round(prob, 1), 'estimated_air': est_air, 'on_track': prob >= 65}


def add_notification(db, user_id, message, ntype='info'):
    db.execute("INSERT INTO notifications (user_id, message, type) VALUES (?,?,?)", (user_id, message, ntype))
    db.commit()


def get_unread_notifications(db, user_id):
    return db.execute(
        "SELECT * FROM notifications WHERE user_id=? AND read=0 ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()
