# Serveur MCP (`jobs-tracker`)

Ce document explique comment configurer et utiliser le serveur **Model Context Protocol (MCP)** intégré à l'application Flask de suivi de candidatures (`jobs-tracker`).

---

## Vue d'ensemble

Le serveur MCP `jobs-tracker` permet à un assistant IA compatible MCP (tel qu'**Antigravity**, Claude Desktop ou Cursor) d'interagir directement avec votre instance locale ou hébergée de l'application Flask :

- Consulter votre profil utilisateur, la complétude de vos coordonnées et votre CV canonique (`static/uploads/users/<user_id>/cvs/cv.json`).
- Lister et inspecter vos candidatures enregistrées dans la table `Job`.
- Ajouter automatiquement une offre d'emploi trouvée ailleurs (par exemple via **Collective Job Search**, **France Travail** ou le web) avec déduplication.
- Enregistrer directement en base SQLite (`Job.cover_letter_text`) la lettre de motivation rédigée par l'assistant et générer son PDF via `tools/document_tools.py`.
- Générer un CV personnalisé au format PDF à partir de votre `cv.json` via le générateur ReportLab du site (`tools/cv_tools.py`), sauvegardé dans `static/uploads/users/<user_id>/generated/` et immédiatement accessible depuis `/generate_cv_pdf/<id>`.

L'implémentation ne nécessite aucune dépendance Python externe supplémentaire (JSON-RPC 2.0 pur).

### Fichiers concernés

- `tools/mcp_jobs.py` : cœur du protocole MCP (`handle_mcp_message`) et implémentation des 7 outils métier.
- `mcp_server.py` : point d'entrée **Stdio** local (redirige `stdout` vers `stderr` avant l'import de `flask_app` pour garantir un flux JSON-RPC propre).
- `flask_app.py` : route **Streamable HTTP** (`GET` / `POST` / `DELETE` sur `/mcp`) protégée par jeton Bearer.
- `config_template.py` : variables de configuration `MCP_API_TOKEN` et `MCP_USER_ID`.
- `test/test_mcp_jobs.py` : suite de tests unitaires isolés (protocole, workflow complet, isolation utilisateur, auth HTTP, smoke test Stdio).

---

## Deux modes de déploiement

### 1. Mode Stdio local (recommandé en local avec Antigravity)

Dans ce mode, Antigravity lance directement `mcp_server.py` en sous-processus via l'environnement virtuel Python du projet. Aucun serveur Flask en cours d'exécution ni aucun jeton réseau n'est nécessaire : le serveur lit et écrit directement dans la base SQLite et le dossier `static/` configurés.

#### Identifier votre `user_id`

Chaque appel MCP est strictement rattaché à l'identifiant utilisateur configuré côté serveur (`JOBS_MCP_USER_ID` ou `MCP_USER_ID`). Vous pouvez vérifier votre identifiant en base SQLite (le premier compte administrateur créé porte généralement l'ID `1`) :

```bash
python3 -c "import sqlite3; conn=sqlite3.connect('instance/jobs.sqlite3'); print(conn.execute('SELECT id, username, email FROM user').fetchall())"
```

#### Configuration dans `~/.gemini/config/mcp_config.json`

Ajoutez l'entrée `jobs-tracker` (ici associée par exemple à `collective-job-search` via `mcp-remote`) :

```json
{
  "mcpServers": {
    "collective-job-search": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://api.collective.work/mcp/talent"
      ]
    },
    "jobs-tracker": {
      "command": "<CHEMIN_PROJET>/.venv/bin/python",
      "args": [
        "<CHEMIN_PROJET>/mcp_server.py"
      ],
      "env": {
        "JOBS_MCP_USER_ID": "1"
      }
    }
  }
}
```

*(Sur macOS avec `nvm`, utilisez le chemin absolu vers `npx` et ajoutez le dossier `bin` correspondant dans `env.PATH` pour les serveurs Node.js.)*

---

### 2. Mode Streamable HTTP (`POST /mcp` sur Flask / PythonAnywhere)

Si votre application tourne sur un serveur distant (ou déjà en local sur un port HTTP), vous pouvez exposer l'endpoint `/mcp` directement via Flask.

#### Activation côté serveur

1. Générez un jeton aléatoire robuste :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. Renseignez ce jeton dans votre `config.py` local (jamais versionné) ou via les variables d'environnement du serveur :

```python
MCP_API_TOKEN = '<JETON_SECRET>'
MCP_USER_ID = 1
```

Variables d'environnement reconnues (prioritaires sur `config.py`) :
- `JOBS_MCP_TOKEN` : jeton Bearer attendu dans l'en-tête `Authorization: Bearer <JETON_SECRET>`.
- `JOBS_MCP_USER_ID` : identifiant numérique de l'utilisateur cible dans la table `user`.

#### Configuration côté client (`mcp_config.json`)

```json
{
  "mcpServers": {
    "jobs-tracker": {
      "url": "https://<VOTRE_DOMAINE>/mcp",
      "headers": {
        "Authorization": "Bearer <JETON_SECRET>"
      }
    }
  }
}
```

#### Comportement de sécurité de `/mcp`

- **Jeton absent dans la configuration** (`MCP_API_TOKEN` et `JOBS_MCP_TOKEN` vides) : l'endpoint est désactivé et répond **HTTP `503`**.
- **En-tête `Authorization: Bearer ...` manquant ou invalide** : répond **HTTP `401`** (comparaison en temps constant via `hmac.compare_digest`).
- **`GET /mcp`** : répond **HTTP `405`** (pas de flux SSE non sollicité).
- **`DELETE /mcp`** : répond **HTTP `204`**.
- **Isolation utilisateur** : les outils ne prennent jamais de `user_id` en paramètre d'entrée ; ils utilisent exclusivement l'identifiant configuré côté serveur, vérifient que le compte n'est pas suspendu (`User.suspended`), et refusent tout accès à une candidature appartenant à un autre utilisateur (`job.user_id != user_id`).

---

## Référence des 7 outils MCP

| Outil | Rôle principal | Paramètres requis | Paramètres optionnels clés |
| :--- | :--- | :--- | :--- |
| `get_profile_and_cv` | Lit le profil utilisateur, l'état des coordonnées et le CV canonique `cv.json` avec les index | *(aucun)* | `include_full_cv` (`bool`, défaut `true`) |
| `list_candidatures` | Liste les candidatures de l'utilisateur | *(aucun)* | `search` (`str`), `only_active` (`bool`), `limit` (`1..100`, défaut `20`) |
| `get_candidature` | Détail complet d'une fiche (`Job`), lettre en base et présence des PDF | `job_id` (`int`) | — |
| `add_candidature` | Ajoute une offre au suivi avec déduplication (`offer_id` puis `url`) | `name`, `company` | `url`, `zip_code`, `contact`, `email`, `offer_id`, `offer_source`, `cover_letter_text`, `application_date` |
| `save_cover_letter` | Enregistre `Job.cover_letter_text` en base et génère le PDF LM | `job_id`, `cover_letter_text` | `generate_pdf` (`bool`, défaut `true`) |
| `generate_cover_letter_pdf` | Génère/regénère le PDF LM depuis le texte stocké en base | `job_id` | — |
| `generate_tailored_cv_pdf` | Génère le CV PDF personnalisé depuis `cv.json` via ReportLab | `job_id` | `cv_title`, `summary`, `highlighted_work_indices`, `highlighted_skill_names`, `highlighted_project_names`, `include_sections`, `selected_education`, `selected_certificates`, `selected_skills`, `selected_projects`, `selected_references` |

### Détails importants par outil

- **`add_candidature`** : `zip_code` accepte soit un code postal (`"06560"`), soit une chaîne de localisation complète (`"06560 Valbonne, France"`), dont le code postal est extrait automatiquement. Si `offer_id` ou `url` correspond déjà à une fiche existante pour cet utilisateur, l'outil renvoie `{"created": false, "already_exists": true, "job_id": ...}` sans créer de doublon.
- **`save_cover_letter`** : utilise `tools.document_tools.generate_cover_letter_pdf_bytes` (LibreOffice headless si installé avec `Cover_letter.dot`/`Cover_letter.dotx`, ou repli ReportLab). En cas d'erreur PDF (ex. coordonnées incomplètes), le texte reste bien enregistré en base et un champ `pdf_warning` est retourné.
- **`generate_tailored_cv_pdf`** : échappe automatiquement les caractères XML spéciaux (`&`, `<`, `>`) dans `cv_title` et `summary` avant le rendu ReportLab, puis écrit le fichier sous :
  `static/uploads/users/<user_id>/generated/CV <Candidat> - <Entreprise> - <Poste>.pdf`
  C'est exactement le chemin vérifié par la route web `/generate_cv_pdf/<id>` dans `flask_app.py`.

---

## Exemple de workflow complet depuis Antigravity

Lorsque `collective-job-search` et `jobs-tracker` sont tous deux actifs dans Antigravity, vous pouvez enchaîner toute la préparation d'une candidature en une conversation :

1. **Trouver une offre** sur Collective avec `collective-job-search` (ex. *« Cherche des CDI QA/Python près de Sophia-Antipolis »*).
2. **Analyser votre profil et votre CV canonique** via `jobs-tracker` (`get_profile_and_cv`).
3. **Demander la création complète du dossier** :
   > *« Ajoute cette offre à mon suivi de candidature, rédige une lettre de motivation adaptée et enregistre-la en base, puis génère mon CV personnalisé en PDF à partir de mon `cv.json`. »*
4. Antigravity appelle successivement :
   - `add_candidature` → crée la fiche en base et récupère le `job_id` ;
   - `save_cover_letter` → stocke le texte en base (`Job.cover_letter_text`) et génère le PDF de lettre ;
   - `generate_tailored_cv_pdf` → sélectionne les expériences, compétences et projets pertinents et génère le CV PDF dans `static/uploads/users/<user_id>/generated/`.

Vous retrouvez ensuite la candidature, le texte de la lettre et les PDF directement sur `/suivi` dans l'interface web Flask.

---

## Prérequis et dépannage

### Prérequis utilisateur

- Disposer d'un **CV canonique** (`static/uploads/users/<user_id>/cvs/cv.json`), importé ou créé via **Gérer mes CV**.
- Avoir renseigné ses **coordonnées obligatoires** dans son compte (`name`, `email`, `phone`, `street`, `postal_code`, `city`) pour autoriser la génération des PDF.

### Les outils n'apparaissent pas dans Antigravity

- Après toute modification de `~/.gemini/config/mcp_config.json`, ouvrez une **nouvelle conversation** ou redémarrez Antigravity afin qu'il recharge la liste des outils MCP.
- Vérifiez la syntaxe JSON du fichier :

```bash
python3 -m json.tool ~/.gemini/config/mcp_config.json
```

### Tester manuellement le serveur Stdio

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n' \
  | JOBS_MCP_USER_ID=1 .venv/bin/python mcp_server.py
```

La sortie standard (`stdout`) doit contenir uniquement deux lignes JSON valides (tous les logs Flask sont redirigés vers `stderr`).

### Tester manuellement l'endpoint HTTP `/mcp`

```bash
curl -sS -X POST "http://127.0.0.1:5000/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JETON_SECRET>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### Lancer les tests automatisés

```bash
.venv/bin/python -m pytest -q test/test_mcp_jobs.py
```
