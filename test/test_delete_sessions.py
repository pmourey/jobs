# Quick integration test for the administrator session actions.
# Run with: PYTHONPATH=. python3 test/test_delete_sessions.py

from datetime import datetime, timedelta
import sys

from werkzeug.security import generate_password_hash
from sqlalchemy import text
from flask_app import app, db
from Model import User, Session


def run_test():
    with app.app_context():
        # Ensure tables exist
        db.create_all()

        # Create admin user via raw SQL to avoid ORM init issues
        hashed = generate_password_hash('password')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.execute(text("""
            INSERT INTO user (username, password, role, creationDate, email, validated)
            VALUES (:username, :password, :role, :creationDate, :email, :validated)
        """), {
            'username': 'ci_admin', 'password': hashed, 'role': 0, 'creationDate': now, 'email': 'ci_admin@example.com', 'validated': True
        })
        db.session.commit()
        admin = User.query.filter_by(username='ci_admin').first()

        # Create sample sessions
        s1 = Session(login_id=admin.id, start=datetime.now() - timedelta(hours=1), client_ip='127.0.0.1', browser_family='Test', browser_version='1.0')
        s2 = Session(login_id=admin.id, start=datetime.now() - timedelta(hours=2), client_ip='127.0.0.1', browser_family='Test', browser_version='1.0')
        db.session.add_all([s1, s2])
        db.session.commit()

        client = app.test_client()
        # Set the authenticated browser session and its database session.
        with client.session_transaction() as sess:
            sess['login_id'] = admin.id
            sess['id'] = s1.id

        resp = client.post('/delete_other_sessions')
        print('HTTP', resp.status_code)

        s1r = Session.query.get(s1.id)
        s2r = Session.query.get(s2.id)
        print('s1.end =', s1r.end)
        print('s2.end =', s2r.end)

        ok = resp.status_code == 200 and s1r.end is None and s2r.end is not None
        # Cleanup
        try:
            if s1r:
                db.session.delete(s1r)
            if s2r:
                db.session.delete(s2r)
            if admin:
                db.session.delete(admin)
            db.session.commit()
        except Exception as e:
            print('Cleanup failed:', e)

        if ok:
            print('OK')
            return 0
        else:
            print('FAIL')
            return 1


if __name__ == '__main__':
    sys.exit(run_test())
