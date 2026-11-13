#!/usr/bin/env python3
"""
Test pour vérifier que le formulaire vide affiche bien un message flash
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import app
from Model import db, User, Session as UserSession
from datetime import datetime

def test_empty_form_shows_flash():
    """Test que le formulaire vide affiche un message flash"""

    with app.test_client() as client:
        with app.app_context():
            # Créer les tables
            db.create_all()

            # Créer un utilisateur admin de test
            test_user = User.query.filter_by(username='test_admin').first()
            if not test_user:
                test_user = User(
                    username='test_admin',
                    email='test@test.com',
                    password='password',
                    creation_date=datetime.now()
                )
                test_user.role = 0  # Admin
                test_user.validated = True
                db.session.add(test_user)
                db.session.commit()

            # Créer une session active pour l'utilisateur
            user_session = UserSession(
                login_id=test_user.id,
                start=datetime.now(),
                client_ip='127.0.0.1',
                browser_family='TestBrowser',
                browser_version='1.0'
            )
            db.session.add(user_session)
            db.session.commit()

            # Se connecter
            with client.session_transaction() as sess:
                sess['login_id'] = test_user.id

            print("📝 Test: POST /new/ avec formulaire complètement vide")
            print("-" * 60)

            # Envoyer un POST vide
            response = client.post('/new/', data={}, follow_redirects=False)

            print(f"Status code: {response.status_code}")
            print(f"\nRéponse contient 'Please enter all the fields': {b'Please enter all the fields' in response.data}")
            print(f"Réponse contient 'alert': {b'alert' in response.data}")
            print(f"Réponse contient 'error': {b'error' in response.data}")

            # Afficher un extrait de la réponse HTML autour du message flash
            if b'Please enter all' in response.data:
                html = response.data.decode('utf-8')
                start_idx = html.find('Please enter all')
                if start_idx > 0:
                    extract = html[max(0, start_idx-200):start_idx+200]
                    print(f"\n📄 Extrait HTML autour du message:")
                    print(extract)

            # Vérifications
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            assert b'Veuillez remplir tous les champs' in response.data or b'Please enter all the fields' in response.data, "Message flash non trouvé dans la réponse"
            assert b'alert' in response.data, "Pas d'élément alert dans la réponse"

            print("\n✅ Le message flash s'affiche correctement!")

            # Test avec seulement le champ 'name' rempli (company manquant)
            print("\n" + "="*60)
            print("📝 Test: POST /new/ avec seulement 'name' rempli")
            print("-" * 60)

            response2 = client.post('/new/', data={'name': 'Test Job'}, follow_redirects=False)
            print(f"Status code: {response2.status_code}")
            print(f"Message flash présent: {b'Veuillez remplir' in response2.data or b'Please enter all' in response2.data}")

            assert response2.status_code == 200
            assert b'Veuillez remplir' in response2.data or b'Please enter all' in response2.data

            # Test avec email invalide
            print("\n" + "="*60)
            print("📝 Test: POST /new/ avec email invalide")
            print("-" * 60)

            response3 = client.post('/new/', data={
                'name': 'Test Job',
                'company': 'Test Company',
                'email': 'invalid-email'
            }, follow_redirects=False)

            print(f"Status code: {response3.status_code}")
            print(f"Message 'Invalid E-Mail' ou 'E-mail invalide' présent: {b'Invalid E-Mail' in response3.data or b'E-mail invalide' in response3.data}")

            assert response3.status_code == 200
            assert b'Invalid E-Mail' in response3.data or b'E-mail invalide' in response3.data

            print("\n✅ Tous les messages flash fonctionnent correctement!")

if __name__ == '__main__':
    try:
        test_empty_form_shows_flash()
    except AssertionError as e:
        print(f"\n❌ Test échoué: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

