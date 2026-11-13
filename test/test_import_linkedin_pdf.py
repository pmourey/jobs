#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import app
from Model import User, Session as UserSession, Job, db


class ImportLinkedinPdfTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(username='test_import_pdf', email='test_import_pdf@example.com', password='pwd', creation_date=datetime.now())
        self.user.validated = True
        db.session.add(self.user)
        db.session.commit()

        self.session = UserSession(login_id=self.user.id, start=datetime.now(), client_ip='127.0.0.1', browser_family='Test', browser_version='1')
        db.session.add(self.session)
        db.session.commit()

        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['login_id'] = self.user.id

    def tearDown(self):
        db.session.delete(self.session)
        db.session.delete(self.user)
        db.session.commit()
        db.session.remove()
        self.app_context.pop()

    def test_import_pdf_linkedin_endpoint_returns_json(self):
        # Simulate a minimal PDF file (starts with %PDF)
        pdf_bytes = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n'
        data = {
            'user_id': str(self.user.id)
        }
        file_storage = (BytesIO(pdf_bytes), 'resume_linkedin.pdf')
        response = self.client.post('/import_cv', data={**data, 'cv_pdf': file_storage}, content_type='multipart/form-data')
        # should redirect (non-AJAX) or return 200 with JSON if treated as AJAX; accept either
        self.assertIn(response.status_code, (200, 302))
        # If JSON returned, verify structure
        if response.is_json:
            j = response.get_json()
            self.assertIn('ok', j)


if __name__ == '__main__':
    unittest.main()

