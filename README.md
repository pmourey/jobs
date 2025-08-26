# Suivi de Candidatures

Application Flask de suivi des candidatures d'emploi avec envoi automatique de relances par email.

## 🌐 Démo en ligne
[http://pmourey.pythonanywhere.com](https://pmourey.pythonanywhere.com/)

## 📋 Fonctionnalités

- **Gestion des candidatures** : Ajout, modification, suppression des offres d'emploi
- **Upload de captures PDF** : Sauvegarde des captures d'écran des offres (max 2Mo)
- **Relances automatiques** : Envoi d'emails de relance mensuels via scheduler
- **Authentification** : Système de comptes utilisateurs avec rôles (Admin/Éditeur/Lecteur)
- **Suivi des sessions** : Historique des connexions utilisateurs
- **Validation email** : Confirmation d'inscription par email

## 🛠️ Installation

### Prérequis
- Python 3.10+ ([Télécharger](https://www.python.org/downloads/))
- Compte Gmail avec mot de passe d'application

### Configuration

1. **Cloner le projet**
   ```bash
   git clone <repository-url>
   cd jobs
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```
   *En cas d'erreur, mettre à jour pip :*
   ```bash
   python -m pip install --upgrade pip
   ```

3. **Configuration email**
   - Créer un mot de passe d'application Gmail
   - Configurer les variables dans `config.py`

## 🚀 Utilisation

### Lancement de l'application
```bash
python flask_app.py
```

### Configuration du scheduler (optionnel)
```python
# Dans config.py
app.config['SCHEDULER'] = True
app.config['SCHEDULER_INTERVAL'] = 3600 * 24  # 24h
```

## 📁 Structure du projet

- `flask_app.py` - Application principale Flask
- `Model.py` - Modèles de données SQLAlchemy
- `Controller.py` - Logique métier et envoi d'emails
- `templates/` - Templates HTML
- `static/` - Fichiers CSS, JS et uploads
- `tools/` - Utilitaires (envoi emails, tâches programmées)

## 🔒 Sécurité

- Validation des fichiers PDF (en-tête + taille)
- Authentification par sessions
- Protection CSRF
- Validation des emails

## 📧 Contact

Pour tout problème : contacter l'auteur

