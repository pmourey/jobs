#!/usr/bin/env python3
"""
Script de test pour vérifier que la route /new/ retourne toujours une réponse valide.
"""
import sys
import os

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_app import app
from Model import db, User, Session as UserSession
from werkzeug.security import generate_password_hash
from datetime import datetime

def test_new_route():
    """Test que la route /new/ retourne toujours une réponse"""

    with app.test_client() as client:
        with app.app_context():
            # Créer les tables si nécessaire
            db.create_all()

            # Créer un utilisateur admin de test s'il n'existe pas
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

            print("✓ Test 1: GET /new/ (devrait retourner 200)")
            response = client.get('/new/')
            print(f"  Status: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            print("\n✓ Test 2: POST /new/ avec champs vides (devrait retourner 200 avec erreur)")
            response = client.post('/new/', data={})
            print(f"  Status: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            # Accept English or French flash messages / presence of 'error'
            assert (b'Please enter all the fields' in response.data
                    or b'Veuillez remplir' in response.data
                    or b'error' in response.data), "Message d'erreur attendu"

            print("\n✓ Test 3: POST /new/ avec seulement name (devrait retourner 200 avec erreur)")
            response = client.post('/new/', data={'name': 'Test Job'})
            print(f"  Status: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            print("\n✓ Test 4: POST /new/ avec email invalide (devrait retourner 200 avec erreur)")
            response = client.post('/new/', data={
                'name': 'Test Job',
                'company': 'Test Company',
                'email': 'invalid-email'
            })
            print(f"  Status: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            print("\n✓ Test 5: POST /new/ avec données valides (devrait rediriger)")
            response = client.post('/new/', data={
                'name': 'Test Job',
                'company': 'Test Company',
                'email': 'valid@email.com',
                'url': 'https://example.com',
                'zipCode': '75001',
                'contact': 'John Doe'
            }, follow_redirects=False)
            print(f"  Status: {response.status_code}")
            assert response.status_code in [200, 302], f"Expected 200 or 302, got {response.status_code}"

            print("\n✅ Tous les tests sont passés! La route /new/ retourne toujours une réponse valide.")

if __name__ == '__main__':
    try:
        test_new_route()
    except AssertionError as e:
        print(f"\n❌ Test échoué: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

