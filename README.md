# Suivi de candidatures

Application monolithique Flask pour organiser une recherche d'emploi, suivre
les candidatures et générer des CV/lettres personnalisés. Les fonctions
principales sont protégées par authentification ; les données de candidature
sont privées par défaut.

## Architecture essentielle

- `flask_app.py` : routes Flask et orchestration de l'application.
- `Model.py` : modèles SQLAlchemy (`User`, `Job`, `Session`, recherches,
  configuration IA, quotas).
- `Controller.py` : authentification, uploads et e-mails.
- `tools/` : CV/LM, PDF, France Travail, fournisseurs IA et quotas.
- `templates/` : interface Jinja2.
- `static/uploads/users/<user_id>/` : données et documents propres à un
  utilisateur.
- `instance/backups/deleted_users/` : archives privées des comptes supprimés.

Le CV de référence est
`static/uploads/users/<user_id>/cvs/cv.json`. Les imports PDF sont réalisés en
deux étapes : extraction, puis chargement explicite dans ce CV canonique.

## Installation locale

```bash
python3 -m pip install -r requirements.txt
cp config_template.py config.py
python3 flask_app.py
```

Configurer au minimum dans `config.py` ou l'environnement :

- `SECRET_KEY` et `SQLALCHEMY_DATABASE_URI` ;
- SMTP (`GMAIL_*`, `SMTP_SERVER`, `SMTP_PORT`) si les e-mails sont utilisés ;
- `FT_CLIENT_ID` et `FT_CLIENT_SECRET` pour France Travail en mode réel ;
- la configuration IA du site (`GITHUB_TOKEN`,
  `GITHUB_MODELS_BASE_URL`, `GITHUB_MODELS_MODEL`) si nécessaire ;
- `AI_CREDENTIALS_MASTER_KEY` pour chiffrer les clés IA personnelles.

`config.py`, les tokens, mots de passe et données utilisateurs ne doivent
jamais être ajoutés au dépôt ou aux journaux.

Les tables sont créées automatiquement. Les colonnes ajoutées au modèle
utilisateur sont complétées par une migration légère au démarrage/requête ;
aucune migration externe n'est actuellement requise.

## Fonctionnalités administrateur

- Une seule instance possède un seul profil Administrateur. Promouvoir un
  utilisateur transfère automatiquement le rôle et rétrograde les autres
  administrateurs.
- **IA et quotas** permet de configurer les fournisseurs, le quota mensuel et
  de traiter les demandes d'augmentation.
- Chaque utilisateur voit son quota IA de l'instance, ses appels utilisés et
  ses appels restants dans `/suivi`. Une clé personnelle utilise les quotas de
  son fournisseur et n'est pas comptabilisée dans le quota du site.
- Depuis **Comptes**, un administrateur peut suspendre/réactiver un compte
  avec un motif.
- La suppression peut archiver les données dans
  `instance/backups/deleted_users/` ou effectuer une purge définitive. Les
  reliquats de fichiers sont nettoyés même si le compte n'existe déjà plus en
  base.

## Quotas IA

Les appels effectués avec la configuration IA du site sont comptés dans
`AiUsage`, par utilisateur et par mois UTC. Le quota global est stocké dans
`AppSetting` sous `ai_site_monthly_quota`; un quota individuel peut être stocké
sous `ai_site_monthly_quota_user_<user_id>`. Le quota par défaut est de
20 appels mensuels par utilisateur.

À quota atteint, les routes IA retournent une erreur HTTP 429. Une demande
peut être envoyée depuis `/suivi` et est visible dans **Admin → IA et quotas**.

## Routes utiles

- `/` : accueil ;
- `/suivi` : candidatures, documents et compteur IA ;
- `/update_account/<id>` : profil, coordonnées et CV ;
- `/france_travail` : recherche d'offres ;
- `/admin/ai-providers` : fournisseurs IA, quotas et demandes ;
- `/accounts` : gestion administrateur des comptes ;
- `/legal` : informations publiques sur les données et la conservation.

## Tests

```bash
python3 -m pytest -q
```

Tests ciblés utiles :

```bash
python3 -m pytest -q test/test_admin_roles.py
python3 -m pytest -q test/test_user_contact_info.py
```

## Documentation complémentaire

- [Fournisseurs IA et crédits](docs/AI_API_PROVIDERS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Configuration Ollama](docs/OLLAMA.md)
- [Projet communautaire](docs/COMMUNITY_PROJECT.md)
- [Relais technique](docs/ANTIGRAVITY_HANDOFF.md)
