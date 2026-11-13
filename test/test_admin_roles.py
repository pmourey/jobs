#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_app import app
from Model import AiQuotaRequest, Role, User, db


class AdminRoleTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

        suffix = datetime.now().strftime('%Y%m%d%H%M%S%f')
        self.admin = self._create_user(f'fifi_{suffix}', 'fifi@example.com', Role.ADMIN)
        self.target = self._create_user(f'target_{suffix}', 'target@example.com', Role.USER)
        self.created_users = [self.admin, self.target]
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        AiQuotaRequest.query.filter(
            AiQuotaRequest.user_id.in_([user.id for user in self.created_users])
        ).delete(synchronize_session=False)
        User.query.filter(User.id.in_([user.id for user in self.created_users])).delete(
            synchronize_session=False
        )
        db.session.commit()
        for path in getattr(self, 'created_backup_dirs', []):
            shutil.rmtree(path, ignore_errors=True)
        self.app_context.pop()

    @staticmethod
    def _create_user(username, email, role):
        user = User(
            username=username,
            password='password',
            creation_date=datetime.now(),
            email=email,
        )
        user.role = role.value
        user.validated = True
        db.session.add(user)
        return user

    def _login(self, user_id):
        with self.client.session_transaction() as session:
            session['login_id'] = user_id

    def test_promoting_user_transfers_the_only_admin_role(self):
        self._login(self.admin.id)

        response = self.client.post(
            f'/update_account/{self.target.id}',
            data={'role': 'Administrateur'},
        )

        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.admin)
        db.session.refresh(self.target)
        self.assertEqual(self.admin.role, Role.USER.value)
        self.assertEqual(self.target.role, Role.ADMIN.value)
        self.assertEqual(User.query.filter_by(role=Role.ADMIN.value).count(), 1)

    def test_admin_cannot_demote_itself_from_its_own_profile(self):
        self._login(self.admin.id)

        response = self.client.post(
            f'/update_account/{self.admin.id}',
            data={'role': 'Utilisateur'},
        )

        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.admin)
        self.assertEqual(self.admin.role, Role.ADMIN.value)

    def test_quota_notification_uses_one_admin_recipient(self):
        duplicate_admin = self._create_user(
            f'legacy_admin_{self.admin.id}',
            f'legacy_admin_{self.admin.id}@example.com',
            Role.ADMIN,
        )
        self.created_users.append(duplicate_admin)
        db.session.commit()
        self._login(self.target.id)
        app.config.update(GMAIL_USER='sender@example.com', GMAIL_APP_PWD='test-password')

        with patch('flask_app.send_email', return_value=True) as send_email:
            response = self.client.post(
                '/ai-quota-request',
                data={'requested_quota': '100', 'reason': 'test'},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(send_email.call_count, 1)
        recipient = send_email.call_args.kwargs['recipient_email']
        self.assertEqual(recipient, min(self.admin.email, duplicate_admin.email))

        self._login(self.admin.id)
        panel = self.client.get('/admin/ai-providers')
        self.assertEqual(panel.status_code, 200)
        panel_html = panel.get_data(as_text=True)
        self.assertIn('Demandes en attente', panel_html)
        self.assertIn(self.target.username, panel_html)
        self.assertIn(self.target.email, panel_html)
        self.assertIn('Demandée le', panel_html)

    def test_admin_can_suspend_and_reactivate_account_with_reason(self):
        self._login(self.admin.id)

        response = self.client.post(
            f'/account/{self.target.id}/suspension',
            data={'action': 'suspend', 'reason': 'Demande de vérification'},
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.target)
        self.assertTrue(self.target.suspended)
        self.assertEqual(self.target.suspension_reason, 'Demande de vérification')

        login_client = app.test_client()
        response = login_client.post(
            '/login',
            data={'username': self.target.username, 'password': 'password'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('suspendu', response.get_data(as_text=True).lower())

        self._login(self.admin.id)
        response = self.client.post(
            f'/account/{self.target.id}/suspension',
            data={'action': 'reactivate'},
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.target)
        self.assertFalse(self.target.suspended)
        self.assertIsNone(self.target.suspension_reason)

    def test_user_can_see_remaining_ai_credits(self):
        self._login(self.target.id)

        response = self.client.get('/suivi')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Crédits IA disponibles', response.get_data(as_text=True))

    def test_archive_delete_removes_account_and_keeps_private_backup(self):
        upload_dir = Path(app.static_folder) / 'uploads' / 'users' / str(self.target.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / 'marker.txt').write_text('private data', encoding='utf-8')
        backup_root = Path(app.instance_path) / 'backups' / 'deleted_users'
        before = set(backup_root.glob('*')) if backup_root.exists() else set()
        self._login(self.admin.id)

        response = self.client.post(
            f'/delete_account/{self.target.id}',
            data={'mode': 'archive'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(User.query.get(self.target.id))
        after = set(backup_root.glob('*'))
        created = after - before
        self.assertEqual(len(created), 1)
        self.created_backup_dirs = created
        backup_dir = next(iter(created))
        self.assertTrue((backup_dir / 'manifest.json').exists())
        self.assertTrue((backup_dir / 'uploads' / 'marker.txt').exists())
        self.assertFalse(upload_dir.exists())

    def test_delete_missing_account_cleans_residual_files(self):
        missing_id = 900000 + self.admin.id
        residual_dir = Path(app.static_folder) / 'uploads' / 'users' / str(missing_id)
        residual_dir.mkdir(parents=True, exist_ok=True)
        (residual_dir / 'orphan.txt').write_text('orphan', encoding='utf-8')
        self._login(self.admin.id)

        response = self.client.post(
            f'/delete_account/{missing_id}',
            data={'mode': 'purge'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(residual_dir.exists())


if __name__ == '__main__':
    unittest.main()
