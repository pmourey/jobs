# Relais de session pour Antigravity

Document de transmission des évolutions réalisées dans cette session. Aucun
secret, token ou contenu de `config.py` ne doit être ajouté à ce document.

## Déploiement et intégrations réseau

- `appscript` et `docx2pdf` ont été retirés de `requirements.txt` car
  `appscript` dépend de macOS (`Carbon/Carbon.h`) et ne peut pas être compilé
  sur PythonAnywhere/Linux.
- `PyPDF2==3.0.1` a été ajouté pour permettre l'extraction de texte des PDF
  LinkedIn sans dépendre d'un parseur externe.
- Les erreurs de connexion à France Travail sont formatées pour expliquer
  clairement un blocage de proxy PythonAnywhere (`403 Forbidden`).
- Les routes de vérification Google, `/sitemap.xml` et `/robots.txt` sont
  disponibles publiquement.
- Les fournisseurs d'offres configurables sont France Travail, Adzuna et
  Jooble. Un utilisateur ne peut pas lancer une recherche si aucun fournisseur
  activé ne possède une configuration complète.

## CV et imports

- Le CV principal est désormais `static/uploads/users/<user_id>/cvs/cv.json`.
- `normalize_cv_data()` impose une structure canonique stable, inspirée de
  JSON Resume.
- `ensure_canonical_cv()` migre les anciens JSON et conserve les fichiers
  sources.
- L'import PDF est volontairement en deux étapes : import/extraction, puis
  action explicite **Charger dans cv.json**.
- `load_pdf_into_canonical()` fusionne les données extraites sans remplacer
  les informations déjà renseignées.
- Le parseur LinkedIn utilise, dans l'ordre, le module local disponible, la
  commande externe puis le fallback `PyPDF2`.
- Les fichiers et routes historiques de fusion sont conservés pour
  compatibilité, mais l'interface principale privilégie le CV canonique unique.

## Génération CV et lettres

- Les boutons et routes de génération CV/LM sont désactivés ou refusés si
  aucun CV canonique n'est disponible.
- Une photo par défaut appartenant à l'administrateur n'est plus utilisée pour
  les autres utilisateurs. Seule la photo personnelle présente dans le dossier
  utilisateur est chargée.
- Le JavaScript des générations IA traite maintenant les réponses HTTP non JSON
  afin d'éviter le message `Unexpected token '<'`.

## Fournisseurs IA, clés et quotas

- `tools/ai_credentials.py` gère les fournisseurs personnels avec stockage
  chiffré par Fernet.
- La clé `AI_CREDENTIALS_MASTER_KEY` doit être stable et conservée hors du
  dépôt. Si elle est changée, les anciennes clés personnelles deviennent
  indéchiffrables.
- Lorsqu'une clé personnelle est absente, invalide ou impossible à déchiffrer,
  l'application tente la configuration IA administrateur (`GITHUB_TOKEN`,
  `GITHUB_MODELS_BASE_URL`, `GITHUB_MODELS_MODEL`).
- Une clé personnelle n'est pas comptabilisée dans le quota de l'API du site.
- Les appels utilisant la configuration administrateur sont comptabilisés dans
  `AiUsage`, par utilisateur et par mois UTC.
- Le quota global est stocké dans `AppSetting` sous
  `ai_site_monthly_quota`. Un quota individuel peut être enregistré sous
  `ai_site_monthly_quota_user_<user_id>`.
- Le quota par défaut est de 20 appels par utilisateur et par mois.
- À quota atteint, les routes IA retournent HTTP 429 avec une réponse JSON
  explicite.
- L'utilisateur peut envoyer une demande d'augmentation via
  `/ai-quota-request`. L'administrateur la traite depuis **Fournisseurs IA**.
- Aucun paiement en ligne n'est implémenté à ce stade ; l'augmentation repose
  sur une validation manuelle.
- Une ancienne clé personnelle impossible à déchiffrer ne doit plus provoquer
  d'erreur 500 sur `/suivi` : elle est journalisée puis le fallback site est
  utilisé.
- `/suivi` affiche désormais les appels utilisés, le quota mensuel et le
  nombre d'appels restants à chaque utilisateur. Le formulaire de demande
  d'augmentation n'est affiché que lorsque la configuration IA du site est
  effectivement utilisée.

## Rôles et cycle de vie des comptes

- Une seule instance possède un seul profil Administrateur. La promotion d'un
  utilisateur depuis **Comptes** transfère le rôle et rétrograde les autres
  administrateurs.
- `User.suspended`, `suspension_reason`, `suspended_at` et `suspended_by`
  permettent de suspendre puis réactiver un compte. Le motif est obligatoire ;
  une connexion et une session existante sont bloquées pour un compte suspendu.
- Les colonnes de suspension sont ajoutées à la table existante `user` par la
  migration légère `_ensure_user_status_columns()` ; `db.create_all()` seul
  n'ajoute pas les colonnes d'une table déjà créée.
- `/delete_account/<user_id>` accepte l'archivage ou la purge. L'archivage
  écrit un manifeste JSON et copie les fichiers dans
  `instance/backups/deleted_users/`, hors du répertoire `static` public.
  La purge supprime les lignes liées, les fichiers utilisateur, les captures
  de candidatures et les réglages de quota individuels.
- La suppression tolère l'absence de la ligne `User` et nettoie néanmoins les
  reliquats associés. Les archives restent des données personnelles et doivent
  être supprimées selon la politique de conservation/RGPD de l'instance.
- L'interface correspondante se trouve dans `templates/accounts.html` ;
  `templates/legal.html` décrit les choix d'archivage, de purge et de
  suspension.

## Modèles et déploiement

- Les modèles `AiUsage` et `AiQuotaRequest` sont créés par le
  `db.create_all()` existant.
- Après déploiement, recharger l'application Flask pour créer les nouvelles
  tables.
- Tester séparément un utilisateur avec clé personnelle et un utilisateur
  utilisant le fallback administrateur.
- `config.py` peut rester hors Git et être copié uniquement sur
  PythonAnywhere, mais les secrets ne doivent jamais être ajoutés à un
  commit, à une documentation ou à un log.

## Fichiers principaux

- `flask_app.py` : routes IA, quotas, imports CV, fournisseurs d'offres et
  routes SEO.
- `Model.py` : `AiUsage`, `AiQuotaRequest` et `UserAiCredential`.
- `tools/ai_credentials.py` : résolution des configurations IA et fallback.
- `tools/ai_quota.py` : comptage et contrôle des quotas.
- `tools/cv_tools.py` : CV canonique, normalisation, extraction et fusion.
- `templates/candidatures.html` : actions CV/LM, compteur et demande de quota.
- `templates/ai_settings.html` : configuration IA personnelle.
- `templates/admin_ai_providers.html` : autorisations, quota global et demandes.
- `templates/accounts.html` : transfert de rôle, suspension et suppression
  avec archivage ou purge.
- `templates/manage_cvs.html` : import et chargement explicite des PDF.
- `README.md` et `docs/AI_API_PROVIDERS.md` : documentation utilisateur et
  technique.

## Vérifications effectuées

- Compilation Python des modules modifiés réussie.
- `git diff --check` réussi.
- Les tests ciblés des rôles, quotas, suspension, archivage et purge passent
  avec `python3 -m pytest -q test/test_admin_roles.py`.
- Le test pytest ciblé des identifiants IA nécessite l'installation de
  `cryptography` dans l'environnement local utilisé pour l'exécution.
