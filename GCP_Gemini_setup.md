# Procédure : Créer un projet GCP / compte de service et activer Generative AI (Gemini)

Ce guide reproduit les commandes utilisées pour configurer l'accès serveur à l'API Generative AI (Gemini) depuis une application Flask.

Remplacez les variables si nécessaire. Les exemples ici utilisent :
- PROJECT_ID=suivi-candidatures
- SERVICE ACCOUNT NAME=generative-ai-sa
- KEY_PATH=/Users/display/keys/generative-ai-sa.json

Pré-requis
- Google Cloud SDK installé (gcloud)
- Être authentifié et avoir la permission d'activer des APIs et gérer IAM (Project Owner ou équivalent)

Étapes

1) Authentification & projet

```bash
gcloud auth login
gcloud config set project suivi-candidatures
```

2) (Optionnel) Lister APIs candidates

```bash
gcloud services list --available | egrep -i "generat|gemini|aiplatform|vertex"
```

3) Activer les APIs recommandées

```bash
gcloud services enable generativelanguage.googleapis.com
gcloud services enable aiplatform.googleapis.com
# (essayez si présent)
gcloud services enable gemini-enterprise-agent.googleapis.com || true
```

4) Créer le compte de service

```bash
export PROJECT_ID="suivi-candidatures"
export SA="generative-ai-sa"
export KEY_PATH="/Users/display/keys/generative-ai-sa.json"

# Create SA
gcloud iam service-accounts create $SA \
  --display-name="Generative AI Service Account" \
  --project="$PROJECT_ID"
```

5) Attribuer rôles minimaux recommandés

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

6) Créer la clé JSON et la protéger

```bash
mkdir -p "$(dirname "$KEY_PATH")"
gcloud iam service-accounts keys create "$KEY_PATH" \
  --iam-account="${SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="$PROJECT_ID"

# Vérifier
ls -l "$KEY_PATH"
# Exporter pour ADC
export GOOGLE_APPLICATION_CREDENTIALS="$KEY_PATH"
```

7) Tester un appel simple (client Python recommandé)

- Installer la librairie officielle :

```bash
pip install --upgrade google-generative-ai google-auth
```

- Test rapide (test_genai.py)

```python
import google.generativeai as genai
# Utilise ADC via GOOGLE_APPLICATION_CREDENTIALS
genai.configure()
resp = genai.models.generate_text(model='models/text-bison-001', prompt='Bonjour, test court.', max_output_tokens=64)
print(getattr(resp, 'text', resp))
```

8) Bonnes pratiques
- Ne pas committer la clé JSON dans Git.
- Utiliser secrets manager / cloud KMS / Kubernetes secrets pour production.
- Créer budget/alertes de facturation (Console → Billing → Budgets & alerts).
- Limiter et logger les appels IA et mettre en place caching.

Dépannage rapide
- Commande gcloud non trouvée → installer Cloud SDK (Homebrew sur macOS : `brew install --cask google-cloud-sdk`).
- Activation API 403 → organisation avec policies restreintes ; contacter l'admin GCP.
- Erreurs d'auth ADC → vérifier que la variable d'environnement GOOGLE_APPLICATION_CREDENTIALS pointe sur le JSON et que le fichier existe.

Si vous devez, je peux générer un script shell automatisé (avec sécurité minimale) ou ajouter un extrait dans `config.py` pour charger automatiquement la variable d'environnement lors du déploiement.

---

Script d'automatisation fourni

Un script exécutable est inclus dans le dépôt : `setup_gcp_gemini.sh`.
Utilisation rapide :

```bash
chmod +x setup_gcp_gemini.sh
./setup_gcp_gemini.sh --project suivi-candidatures --sa generative-ai-sa --key-path /Users/display/keys/generative-ai-sa.json
```

Le script :
- vérifie la présence de `gcloud`
- active les APIs recommandées (si possible)
- crée le compte de service
- attribue les rôles recommandés
- crée la clé JSON à l'emplacement demandé (avec confirmation si elle existe)

Notes de sécurité :
- le script n'enregistre ni n'envoie la clé à aucun service externe.
- gardez la clé hors dépôt et limitez son accès système.

Besoin d'une version qui enregistre la clé dans un secret manager (GCP Secret Manager, Kubernetes secret) ? Réponds "Oui" ou "Non".