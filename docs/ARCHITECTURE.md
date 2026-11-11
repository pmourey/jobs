# Architecture technique

## Vue d'ensemble

L'application est un monolithe Flask :

```text
Navigateur
   │
   ├── templates/ + static/
   │
   └── flask_app.py
          ├── Model.py / SQLAlchemy / SQLite
          ├── Controller.py (authentification, e-mails, uploads)
          └── tools/
                 ├── cv_tools.py
                 ├── document_tools.py
                 ├── france_travail.py
                 └── jobboard_providers.py
```

## Flux principaux

### Compte et sessions

Les comptes et les sessions sont stockés en base SQLAlchemy. Les routes protégées utilisent les décorateurs d'accès présents dans `flask_app.py`. Les sessions enregistrent notamment l'utilisateur, l'adresse IP et des informations de navigateur ; leur gestion et leur durée doivent être configurées avec la politique de conservation du déploiement.

### Candidatures et documents

Les candidatures sont stockées dans la base. Les CV sources et les fichiers générés sont rangés par utilisateur sous `static/uploads/users/{user_id}/`. Les captures sont validées avant stockage. La génération PDF est réalisée côté serveur avec ReportLab.

### IA

Les routes CV/LM appellent `tools.cv_tools` et `tools.document_tools`. Le client IA utilise un endpoint compatible configuré dans `config.py`; Ollama local est documenté dans [OLLAMA.md](OLLAMA.md). Les replis locaux doivent être conservés pour permettre les tests hors réseau.

### France Travail

`tools/france_travail.py` obtient un jeton OAuth2 puis appelle l'API France Travail. Les offres sont normalisées, dédupliquées, enrichies avec le matching et stockées dans une recherche utilisateur. Les identifiants `FT_CLIENT_ID` et `FT_CLIENT_SECRET` ne doivent jamais être exposés au navigateur.

## Déploiement et protection

- utiliser une vraie `SECRET_KEY` hors du dépôt ;
- stocker les secrets dans l'environnement ou un gestionnaire de secrets ;
- servir l'application derrière HTTPS et un proxy correctement configuré ;
- limiter l'accès aux répertoires de fichiers utilisateurs ;
- désactiver le mode debug en production ;
- sauvegarder et chiffrer les bases et documents selon le niveau de sensibilité ;
- documenter les sous-traitants, les transferts et les durées de conservation ;
- tester les procédures de suppression, restauration et réponse aux demandes RGPD.

La page publique `/legal` fournit une base d'information utilisateur, mais l'exploitant reste responsable de sa mise en conformité et de sa validation juridique.
