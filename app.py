import sqlite3
import os
from functools import wraps
from flask import Flask, g, session, redirect, url_for

DATABASE = os.path.join(os.path.dirname(__file__), 'gate_mission.db')

def create_app():
    app = Flask(__name__)
    app.secret_key = 'gate-mission-air-100-secret-2027'

    def get_db():
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(DATABASE)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA foreign_keys=ON")
        return db

    @app.teardown_appcontext
    def close_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    app.get_db = get_db

    # Init DB
    with app.app_context():
        from db import init_db
        init_db(get_db())

    # Register blueprints
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.study import study_bp
    from blueprints.revision import revision_bp
    from blueprints.analytics import analytics_bp
    from blueprints.mock_test import mock_bp
    from blueprints.pyq import pyq_bp
    from blueprints.profile import profile_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(study_bp, url_prefix='/study')
    app.register_blueprint(revision_bp, url_prefix='/revision')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    app.register_blueprint(mock_bp, url_prefix='/mock')
    app.register_blueprint(pyq_bp, url_prefix='/pyq')
    app.register_blueprint(profile_bp, url_prefix='/profile')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
