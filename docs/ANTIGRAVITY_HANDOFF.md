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
  Jooble. Adzuna est activé dans le modèle de configuration mais devient
  utilisable uniquement après renseignement de `ADZUNA_APP_ID` et
  `ADZUNA_APP_KEY`. Un utilisateur ne peut pas lancer une recherche si aucun
  fournisseur activé ne possède une configuration complète.
- Jooble est disponible comme source de recherche manuelle. Sa clé est fournie
  par `JOOBLE_API_KEY` dans l'environnement ou `config.py`, avec
  `JOOBLE_BASE_URL=https://fr.jooble.org/api`, puis Jooble doit être activé par
  un administrateur. Les mots-clés sont regroupés en une seule requête pour
  limiter les appels du forfait gratuit. Le quota journalier et le seuil de
  blocage des utilisateurs non administrateurs sont configurables avec
  `JOOBLE_DAILY_QUOTA`, `JOOBLE_QUOTA_THRESHOLD_PERCENT` et le menu
  d'administration des fournisseurs.
- Adzuna est limité à 25 requêtes par mois par défaut
  (`ADZUNA_MONTHLY_QUOTA`). Le seuil de blocage des utilisateurs non
  administrateurs est configurable via `ADZUNA_QUOTA_THRESHOLD_PERCENT` ou
  depuis l'administration ; les compteurs mensuels sont stockés dans
  `AppSetting`.
- Les quotas Jooble et Adzuna sont partagés entre les utilisateurs non
  administrateurs. L'administrateur peut répartir les allocations par compte
  depuis **Fournisseurs d'offres** ; les allocations par défaut sont calculées
  à parts égales et les compteurs individuels sont stockés dans `AppSetting`.

## CV et imports

- Le CV principal est désormais `static/uploads/users/<user_id>/cvs/cv.json`.
- `normalize_cv_data()` impose une structure canonique stable, inspirée de
  JSON Resume.
- `ensure_canonical_cv()` migre les anciens JSON et conserve les fichiers
  sources.
- Les imports PDF, DOCX et ODT extraient le texte localement puis le convertissent
  via l'IA configurée par le site vers `cv.json`. Une absence de configuration,
  de quota ou une réponse IA invalide bloque la conversion avec une erreur explicite.
- Les sources compatibles sont GitConnected (JSON Resume), LinkedIn Export (PDF)
  et les autres CV PDF, DOCX ou ODT.
- Les champs de date canoniques (`date`, `startDate`, `endDate`) sont normalisés
  en `YYYY-MM-DD` pour les contrôles HTML de type date. Les dates limitées au
  mois ou à l'année utilisent le premier jour connu.
- Chaque original est archivé dans
  `static/uploads/users/<user_id>/cvs/originals/` sous le nom fixe
  `original_cv.<format>`. Il n'existe qu'un CV canonique et un original courant
  par utilisateur ; un nouvel import remplace les deux représentations. Le
  manifeste `cvs_meta.json` et une route authentifiée permettent de basculer
  entre l'affichage du CV converti et de l'original.
- Les routes historiques d'import PDF et de chargement manuel restent conservées
  pour compatibilité avec les anciens clients.
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
  l'application tente la configuration IA administrateur (`GEMINI_API_KEY`,
  `GEMINI_BASE_URL`, `GEMINI_MODEL`).
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

## Sessions administrateur

Le panneau **Sessions** mémorise l'identifiant de la session Flask courante.
Un administrateur peut fermer toutes les autres sessions actives via
`POST /delete_other_sessions`; la session qui exécute la demande reste active.
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

## Serveur MCP (`jobs-tracker`)

- `tools/mcp_jobs.py` : implémente le serveur JSON-RPC 2.0 MCP sans dépendance
  externe supplémentaire, lié à un `user_id` configuré côté serveur (par défaut
  `1`, ou via `JOBS_MCP_USER_ID` / `MCP_USER_ID`).
- Outils exposés : `get_profile_and_cv`, `list_candidatures`,
  `get_candidature`, `add_candidature`, `save_cover_letter`,
  `generate_cover_letter_pdf` et `generate_tailored_cv_pdf` (qui réutilise
  `generate_tailored_cv_pdf_bytes` et sauvegarde dans
  `static/uploads/users/<user_id>/generated/`).
- `mcp_server.py` : point d'entrée Stdio local (redirige `stdout` vers `stderr`
  avant l'import de `flask_app` pour garder le flux JSON-RPC propre).
- `POST /mcp` dans `flask_app.py` : endpoint Streamable HTTP optionnel,
  désactivé (HTTP 503) tant que `MCP_API_TOKEN` / `JOBS_MCP_TOKEN` est vide,
  et protégé par jeton Bearer.
- `test/test_mcp_jobs.py` : tests unitaires isolés (protocole, workflow complet,
  isolation utilisateur, auth HTTP et smoke test Stdio).

## Vérifications effectuées

- Compilation Python des modules modifiés réussie.
- `git diff --check` réussi.
- Les tests ciblés des rôles, quotas, suspension, archivage et purge passent
  avec `python3 -m pytest -q test/test_admin_roles.py`.
- Le test pytest ciblé des identifiants IA nécessite l'installation de
  `cryptography` dans l'environnement local utilisé pour l'exécution.
