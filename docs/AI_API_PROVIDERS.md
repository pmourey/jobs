# Fournisseurs IA utilisables par API

## Recommandation pour le projet communautaire

Permettre à un utilisateur d'utiliser sa propre clé API peut être pertinent pour une instance communautaire :

- le projet n'a pas à financer les appels IA ;
- l'utilisateur choisit son fournisseur, son modèle et son budget ;
- les quotas et conditions du fournisseur restent à la charge de l'utilisateur ;
- une instance gratuite peut désactiver les appels distants par défaut.

Cela ne supprime pas les risques de confidentialité. Une clé personnelle ne doit jamais être envoyée au navigateur, écrite dans les logs, stockée en clair dans SQLite ou placée dans un cookie.

## Fournisseurs à étudier

Les prix et conditions changent régulièrement. Vérifier la page officielle avant d'ajouter un fournisseur.

| Fournisseur | API | Intérêt | Points à vérifier |
|---|---|---|---|
| Google Gemini | API Gemini / SDK Google | modèles rapides, offre de démarrage, bons modèles multilingues | utilisation des données du niveau gratuit, quotas, localisation et DPA |
| OpenAI | API compatible SDK OpenAI | intégration connue, modèles variés, outils structurés | prix, rétention, transferts et limites par clé |
| Mistral | API Mistral | acteur européen, français, modèles économiques | modèle choisi, conservation, DPA et région de traitement |
| OpenRouter | API compatible OpenAI | accès à de nombreux modèles et plafonds de dépense | fournisseur réellement sélectionné, rétention et politique no-training |
| Groq | API compatible OpenAI | inférence rapide sur certains modèles | modèles disponibles, quotas et conditions d'utilisation |
| Ollama | API locale | aucun coût par token, données conservées localement | machine nécessaire, performances, disponibilité de l'instance |

Références de départ :

- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [OpenRouter limits](https://openrouter.ai/docs/api-reference/limits)
- [OpenAI API pricing](https://platform.openai.com/docs/pricing)
- [Mistral AI pricing](https://mistral.ai/technology/)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)

## Architecture recommandée pour une clé personnelle

### Étape 1 — Sans stockage

Le formulaire demande le fournisseur et la clé uniquement pour une opération ponctuelle. La clé reste dans la requête HTTPS, est utilisée côté serveur, puis est supprimée de la mémoire applicative dès que possible. Elle ne doit pas être conservée dans la session Flask, car les sessions signées peuvent contenir des données côté cookie selon la configuration.

Cette étape est plus simple à mettre en œuvre, mais l'utilisateur doit ressaisir sa clé.

### Étape 2 — Stockage chiffré facultatif

Si la persistance est nécessaire :

1. chiffrer la clé avec une clé maîtresse fournie par l'environnement ;
2. stocker uniquement le ciphertext et les métadonnées non sensibles ;
3. masquer la clé après enregistrement ;
4. permettre sa suppression immédiate ;
5. ne jamais l'afficher dans une page, un export ou un log ;
6. invalider le cache et les tâches en attente lors de la suppression ;
7. documenter le traitement dans la politique de confidentialité.

La clé maîtresse ne doit pas être stockée dans la base utilisateur ni dans le dépôt. Une rotation de clé et une procédure de récupération doivent être prévues avant production.

## Limites fonctionnelles à imposer

- plafonnement du nombre de requêtes et des tokens par opération ;
- timeout et annulation des tâches ;
- contrôle de taille des CV transmis ;
- choix explicite entre IA locale et fournisseur distant ;
- avertissement avant envoi d'un CV à un fournisseur externe ;
- aucune réutilisation de la clé pour un autre utilisateur ;
- aucun appel automatique sans action explicite de l'utilisateur ;
- journalisation de l'identifiant du fournisseur et du coût estimé, jamais de la clé ni du prompt complet.

## Fonctionnement actuel

La page **Mon compte → Configuration IA** permet maintenant de sélectionner
un fournisseur autorisé et d'enregistrer une clé personnelle chiffrée. La clé
maîtresse est obligatoire et doit rester hors du dépôt :

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export AI_CREDENTIALS_MASTER_KEY='...'
```

La perte de cette clé rend les clés enregistrées indéchiffrables. Elle doit
donc être sauvegardée dans le gestionnaire de secrets de l'hébergeur, jamais
dans `config.py` ou Git. L'administrateur gère la liste blanche depuis
**Fournisseurs IA** ; Ollama reste désactivé par défaut pour PythonAnywhere.
