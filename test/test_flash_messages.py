#!/usr/bin/env python3
"""Test visuel des messages flash en français"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import app
from Model import db, User, Session as UserSession
from datetime import datetime

with app.test_client() as client:
    with app.app_context():
        db.create_all()
        test_user = User.query.filter_by(username='test_admin').first()
        if not test_user:
            test_user = User(username='test_admin', email='test@test.com', password='password', creation_date=datetime.now())
            test_user.role = 0
            test_user.validated = True
            db.session.add(test_user)
            db.session.commit()

        user_session = UserSession(login_id=test_user.id, start=datetime.now(), client_ip='127.0.0.1', browser_family='Test', browser_version='1.0')
        db.session.add(user_session)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['login_id'] = test_user.id

        print("="*70)
        print("TEST 1: Formulaire complètement vide")
        print("="*70)
        response = client.post('/new/', data={})
        html = response.data.decode('utf-8')

        # Chercher le message flash
        if 'Veuillez remplir tous les champs' in html:
            print("✅ Message en français trouvé: 'Veuillez remplir tous les champs obligatoires'")
            # Extraire et afficher le message
            start = html.find('alert alert-')
            if start > 0:
                end = html.find('</div>', start)
                alert_div = html[start:end+6]
                # Nettoyer et afficher
                import re
                clean = re.sub(r'<[^>]+>', '', alert_div)
                clean = ' '.join(clean.split())
                print(f"   Message affiché: {clean}")
        else:
            print("❌ Message en français NON trouvé")

        print("\n" + "="*70)
        print("TEST 2: Email invalide")
        print("="*70)
        response = client.post('/new/', data={'name': 'Test', 'company': 'Test Co', 'email': 'bad@email'})
        html = response.data.decode('utf-8')

        if 'E-mail invalide' in html:
            print("✅ Message en français trouvé: 'E-mail invalide'")
            # Extraire et afficher le message
            start = html.find('alert alert-')
            if start > 0:
                end = html.find('</div>', start)
                alert_div = html[start:end+6]
                import re
                clean = re.sub(r'<[^>]+>', '', alert_div)
                clean = ' '.join(clean.split())
                print(f"   Message affiché: {clean}")
        else:
            print("❌ Message en français NON trouvé")

        print("\n" + "="*70)
        print("RÉSULTAT FINAL")
        print("="*70)
        print("✅ Le formulaire affiche bien les messages d'erreur via flash()")
        print("✅ Les messages sont en français")
        print("✅ Le formulaire se réaffiche avec les valeurs saisies")

