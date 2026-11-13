#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import unquote
from zipfile import ZipFile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_app import app
from Model import Job, Session as UserSession, User, db
from tools.document_tools import (_build_cover_letter_pdf_paragraphs,
                                  build_cover_letter_context,
                                  convert_docx_to_pdf,
                                  render_cover_letter_docx,
                                  resolve_cover_letter_template_path)


class GenerateCoverLetterPdfTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

        unique = datetime.now().strftime('%Y%m%d%H%M%S%f')
        self.username = f'test_pdf_{unique}'
        self.email = f'{self.username}@example.com'

        self.user = User(
            username=self.username,
            email=self.email,
            password='password',
            creation_date=datetime.now(),
        )
        self.user.role = 0
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

        from tools.cv_tools import save_user_contact_info
        save_user_contact_info(self.user.id, {
            'name': 'Test User',
            'email': self.email,
            'phone': '06 12 34 56 78',
            'street': '1 rue de la Paix',
            'postal_code': '06000',
            'city': 'Nice',
        }, app.static_folder)

        self.job = Job(
            name='Developpeur Python',
            url='https://example.com/job',
            zipCode='Nice',
            company='Acme Conseil',
            contact='Jane Doe',
            date=datetime(2026, 6, 1),
            email='jane.doe@example.com',
            user_id=self.user.id,
        )
        self.job.cover_letter_text = 'Je souhaite mettre mon experience Flask au service de votre entreprise.'
        db.session.add(self.job)
        db.session.commit()

        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['login_id'] = self.user.id

    def tearDown(self):
        import shutil
        user_dir = Path(app.static_folder) / 'uploads' / 'users' / str(self.user.id)
        if user_dir.exists():
            shutil.rmtree(user_dir, ignore_errors=True)
        db.session.delete(self.job)
        db.session.delete(self.active_session)
        db.session.delete(self.user)
        db.session.commit()
        db.session.remove()
        self.app_context.pop()

    def test_render_cover_letter_docx_replaces_all_placeholders(self):
        template_path = Path('/static/Cover_letter.dotx')
        replacements = build_cover_letter_context(self.job, datetime(2026, 6, 23))

        with TemporaryDirectory() as tmpdir:
            output_docx = Path(tmpdir) / 'cover_letter.docx'
            render_cover_letter_docx(template_path, output_docx, replacements)

            with ZipFile(output_docx) as archive:
                xml = archive.read('word/document.xml').decode('utf-8', errors='ignore')

        self.assertIn('Acme Conseil', xml)
        self.assertIn('Nice', xml)
        self.assertIn('Developpeur Python', xml)
        self.assertIn('23 juin 2026', xml)
        self.assertIn('Je souhaite mettre mon experience Flask au service de votre entreprise.', xml)
        for placeholder in ('[COMPANY]', '[LOCATION]', '[Intitul poste]', '[LM]', '[Date]'):
            self.assertNotIn(placeholder, xml)

    def test_build_cover_letter_pdf_paragraphs_keeps_intentional_line_breaks(self):
        self.job.cover_letter_text = (
            'Madame, Monsieur,\n'
            'Je souhaite rejoindre votre entreprise.\n'
            'Mon experience en Python et Flask est solide.\n\n'
            'Je vous remercie pour votre attention.\n'
            'Cordialement,'
        )

        paragraphs = _build_cover_letter_pdf_paragraphs(self.job)

        self.assertEqual(
            paragraphs,
            [
                'Madame, Monsieur,\nJe souhaite rejoindre votre entreprise.\nMon experience en Python et Flask est solide.',
                'Je vous remercie pour votre attention.\nCordialement,',
            ],
        )

    def test_build_cover_letter_pdf_paragraphs_merges_pdf_soft_wraps_and_keeps_signoff_newline(self):
        self.job.cover_letter_text = (
            'Madame, Monsieur,\n'
            'Je suis convaincu que mes compétences techniques et mon expérience dans le domaine informatique me\n'
            "permettent d'être un candidat idéal pour le poste visé.\n"
            'Cordialement,\n'
            'Philippe Mourey'
        )

        paragraphs = _build_cover_letter_pdf_paragraphs(self.job)

        self.assertEqual(
            paragraphs,
            [
                "Madame, Monsieur,\nJe suis convaincu que mes compétences techniques et mon expérience dans le domaine informatique me permettent d'être un candidat idéal pour le poste visé.\nCordialement,\nPhilippe Mourey",
            ],
        )

    def test_generate_cover_letter_pdf_bytes_prefers_libreoffice_pipeline_when_available(self):
        fake_pdf = b'%PDF-1.4\nfake'
        self.job.cover_letter_text = 'Ligne 1\nLigne 2\n\nParagraphe 2'

        def _fake_convert(docx_path, pdf_path):
            Path(pdf_path).write_bytes(fake_pdf)
            return Path(pdf_path)

        with patch('tools.document_tools._find_soffice_binary', return_value='/Applications/LibreOffice.app/Contents/MacOS/soffice'), \
                patch('tools.document_tools.render_cover_letter_docx') as render_docx_mock, \
                patch('tools.document_tools.convert_docx_to_pdf', side_effect=_fake_convert):
            from tools.document_tools import generate_cover_letter_pdf_bytes
            pdf_bytes = generate_cover_letter_pdf_bytes(self.job, Path('/static/Cover_letter.dotx'), datetime(2026, 6, 23))

        self.assertEqual(pdf_bytes, fake_pdf)
        render_replacements = render_docx_mock.call_args.args[2]
        self.assertEqual(render_replacements['[LM]'], 'Ligne 1 Ligne 2\n\nParagraphe 2')

    def test_resolve_cover_letter_template_prefers_dot_file(self):
        template_path = resolve_cover_letter_template_path('/static')
        self.assertEqual(template_path.name, 'Cover_letter.dot')

    def test_generate_cover_letter_pdf_endpoint_can_build_url(self):
        with app.test_request_context():
            from flask import url_for

            self.assertEqual(url_for('generate_cover_letter_pdf', id=self.job.id), f'/generate_cover_letter_pdf/{self.job.id}')

    def test_show_all_renders_cover_letter_pdf_link(self):
        response = self.client.get('/suivi')

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'/generate_cover_letter_pdf/{self.job.id}'.encode(), response.data)

    def test_generate_cover_letter_pdf_route_returns_pdf_with_expected_filename(self):
        with patch('tools.document_tools._find_soffice_binary', return_value=None):
            response = self.client.get(f'/generate_cover_letter_pdf/{self.job.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/pdf')
        self.assertTrue(response.data.startswith(b'%PDF'))
        content_disposition = unquote(response.headers.get('Content-Disposition', ''))
        self.assertIn('Lettre motivation Acme Conseil - Developpeur Python.pdf', content_disposition)

    def test_convert_docx_to_pdf_requires_libreoffice(self):
        with TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / 'cover_letter.docx'
            pdf_path = Path(tmpdir) / 'cover_letter.pdf'
            docx_path.write_bytes(b'dummy')

            with patch('tools.document_tools._find_soffice_binary', return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    convert_docx_to_pdf(docx_path, pdf_path)

        self.assertIn('sans ouvrir Word', str(ctx.exception))
        self.assertIn('LibreOffice', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()



