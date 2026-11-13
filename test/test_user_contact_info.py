#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_app import app
from Model import Job, Session as UserSession, User, db
from tools.cv_tools import (
    get_user_contact_info,
    save_user_contact_info,
    validate_user_contact_info,
)


class UserContactInfoTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

        unique = datetime.now().strftime('%Y%m%d%H%M%S%f')
        self.username = f'alice_{unique}'
        self.email = f'{self.username}@example.com'

        self.user = User(
            username=self.username,
            email=self.email,
            password='password',
            creation_date=datetime.now(),
        )
        self.user.role = 1  # EDITOR
        self.user.validated = True
        db.session.add(self.user)
        db.session.commit()

        self.active_session = UserSession(
            login_id=self.user.id,
            start=datetime.now(),
            client_ip='127.0.0.1',
            browser_family='TestBrowser',
            browser_version='1.0',
        )
        db.session.add(self.active_session)
        db.session.commit()

        self.job = Job(
            name='Ingénieur Python',
            url='https://example.com/job',
            zipCode='75001',
            company='Acme Corp',
            contact='RH Acme',
            date=datetime.now(),
            email='jobs@acme.com',
            user_id=self.user.id,
        )
        db.session.add(self.job)
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        # Clean up any created files in uploads/users/<self.user.id>
        user_dir = Path(app.static_folder) / 'uploads' / 'users' / str(self.user.id)
        if user_dir.exists():
            shutil.rmtree(user_dir, ignore_errors=True)
        try:
            db.session.rollback()
            Job.query.filter_by(user_id=self.user.id).delete()
            UserSession.query.filter_by(login_id=self.user.id).delete()
            User.query.filter_by(id=self.user.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
        self.app_context.pop()

    def test_contact_validation_incomplete_for_new_user(self):
        is_complete, missing, info = validate_user_contact_info(self.user.id, app.static_folder)
        self.assertFalse(is_complete)
        self.assertIn('Numéro de téléphone', missing)
        self.assertIn('Adresse postale', missing)

    def test_save_and_retrieve_contact_info(self):
        email_addr = f'alice_{self.user.id}@test.org'
        contact_data = {
            'name': 'Alice Dupont',
            'email': email_addr,
            'phone': '06 12 34 56 78',
            'street': '12 rue de la Paix',
            'postal_code': '75001',
            'city': 'Paris',
        }
        res = save_user_contact_info(self.user.id, contact_data, app.static_folder)
        self.assertTrue(res)

        # Retrieve and verify
        retrieved = get_user_contact_info(self.user.id, app.static_folder)
        self.assertEqual(retrieved['name'], 'Alice Dupont')
        self.assertEqual(retrieved['email'], email_addr)
        self.assertEqual(retrieved['phone'], '06 12 34 56 78')
        self.assertEqual(retrieved['street'], '12 rue de la Paix')
        self.assertEqual(retrieved['postal_code'], '75001')
        self.assertEqual(retrieved['city'], 'Paris')

        # Check validation passes
        is_complete, missing, _ = validate_user_contact_info(self.user.id, app.static_folder)
        self.assertTrue(is_complete)
        self.assertEqual(missing, [])

    def test_routes_enforce_complete_profile_when_missing(self):
        # Set session cookie
        with self.client.session_transaction() as sess:
            sess['login_id'] = self.user.id
            sess['id'] = self.active_session.id

        # 1. preview_cv_data should return 400 with profile_incomplete
        res = self.client.post(f'/preview_cv_data/{self.job.id}')
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertTrue(data.get('profile_incomplete'))
        self.assertIn('Numéro de téléphone', data.get('missing_fields', []))

        # 2. preview_lm_ai should return 400 with profile_incomplete
        res = self.client.post(f'/preview_lm_ai/{self.job.id}')
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertTrue(data.get('profile_incomplete'))

        # 3. generate_cover_letter_pdf should redirect with flash
        res = self.client.get(f'/generate_cover_letter_pdf/{self.job.id}', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/update_account', res.headers['Location'])

    def test_routes_succeed_and_use_candidate_info_when_profile_complete(self):
        email_addr = f'alice_complete_{self.user.id}@test.org'
        # Complete profile for Alice
        save_user_contact_info(self.user.id, {
            'name': 'Alice Dupont',
            'email': email_addr,
            'phone': '06 11 22 33 44',
            'street': '5 Boulevard Voltaire',
            'postal_code': '75011',
            'city': 'Paris',
        }, app.static_folder)

        with self.client.session_transaction() as sess:
            sess['login_id'] = self.user.id
            sess['id'] = self.active_session.id

        # 1. preview_cv_data returns 200 and has Alice's basics
        res = self.client.post(f'/preview_cv_data/{self.job.id}')
        self.assertEqual(res.status_code, 200)
        cv_data = res.get_json().get('cv_data', {})
        basics = cv_data.get('basics', {})
        self.assertEqual(basics.get('name'), 'Alice Dupont')
        self.assertEqual(basics.get('phone'), '06 11 22 33 44')
        self.assertNotIn('Philippe Mourey', json.dumps(basics))
        self.assertNotIn('06 89 15 08 56', json.dumps(basics))

        # 2. generate_cover_letter_pdf returns 200 PDF without Philippe Mourey
        res = self.client.get(f'/generate_cover_letter_pdf/{self.job.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/pdf')
        # Check that PDF bytes do not contain Philippe Mourey or Philippe's phone
        pdf_bytes = res.data
        self.assertNotIn(b'Philippe Mourey', pdf_bytes)
        self.assertNotIn(b'06 89 15 08 56', pdf_bytes)
        self.assertNotIn(b'philippe.mourey@gmail.com', pdf_bytes)

    def test_update_account_get_and_post_contact_info(self):
        with self.client.session_transaction() as sess:
            sess['login_id'] = self.user.id
            sess['id'] = self.active_session.id

        # GET update_account shows contact fields
        res = self.client.get(f'/update_account/{self.user.id}')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Coordonnées du profil', html)
        self.assertIn('numéro de téléphone', html.lower())

        # POST update_account updates contact info
        post_data = {
            'username': self.user.username,
            'name': 'Alice Dupont-Martin',
            'email': f'alice_dm_{self.user.id}@test.org',
            'phone': '06 99 88 77 66',
            'street': '10 rue de Rivoli',
            'postal_code': '75004',
            'city': 'Paris',
        }
        res = self.client.post(f'/update_account/{self.user.id}', data=post_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check saved info
        info = get_user_contact_info(self.user.id, app.static_folder)
        self.assertEqual(info['name'], 'Alice Dupont-Martin')
        self.assertEqual(info['email'], f'alice_dm_{self.user.id}@test.org')
        self.assertEqual(info['phone'], '06 99 88 77 66')
        self.assertEqual(info['city'], 'Paris')


if __name__ == '__main__':
    unittest.main()
