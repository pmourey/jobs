# IA locale avec Ollama

Cette configuration est destinée aux administrateurs ou développeurs qui souhaitent exécuter l'assistance IA localement. Elle n'est pas nécessaire pour utiliser le suivi de candidatures de base.

## Installation

Sur macOS :

```bash
brew install ollama
ollama serve
ollama pull llama3.1:8b
```

Vérifier le serveur :

```bash
curl -s http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ollama-local" \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"Dis bonjour en français"}]}'
```

## Configuration Flask

Dans une copie locale de `config.py` :

```python
GITHUB_TOKEN = 'ollama-local'
GITHUB_MODELS_BASE_URL = 'http://localhost:11434'
GITHUB_MODELS_MODEL = 'llama3.1:8b'
ENABLE_REMOTE_IA = True
OLLAMA_LOCAL_TUNING = IMAC_64GB_OLLAMA_TUNING
```

`GITHUB_TOKEN` est conservé comme nom de configuration historique ; il ne s'agit pas d'un token envoyé à Ollama local. Ne publiez pas de vraie clé dans `config.py`.

Le preset `ollama_tuning.py` peut ajuster les threads, le contexte, le nombre maximal de tokens et le délai d'attente. Adaptez-le aux ressources de la machine plutôt que de reprendre un preset sans mesure.

## Confidentialité

Avec Ollama local, les prompts sont envoyés à l'instance configurée sur la machine. Avec un endpoint distant compatible, vérifiez la politique du fournisseur, la conservation des prompts, les sous-traitants et la localisation des données avant d'y envoyer un CV ou une candidature.

Si l'IA distante est désactivée (`ENABLE_REMOTE_IA = False`), l'application utilise les replis locaux prévus par les parcours concernés.
