# Projet communautaire gratuit

Ce document décrit la trajectoire de `jobs` vers un projet open source gratuit. Il ne constitue pas un avis juridique, fiscal ou comptable.

## Principes

- Le logiciel reste disponible gratuitement.
- Le code source et les instructions d'auto-hébergement sont publics.
- Aucun paiement n'est nécessaire pour créer un compte ou utiliser une fonctionnalité.
- Une contribution financière éventuelle est facultative et ne donne droit à aucune fonctionnalité, priorité de support ou garantie de disponibilité.
- Les données personnelles et les documents des utilisateurs restent protégés même lorsque le service est gratuit.
- Aucun lien de soutien ne doit être configuré tant que le bénéficiaire, les conditions du prestataire et le traitement fiscal n'ont pas été vérifiés.

## Phase 1 — Projet communautaire gratuit

### Objectif

Fournir une instance gratuite et publier le code afin de recueillir des retours, sans abonnement, crédits payants ni fonctionnalité réservée aux contributeurs.

### Mise en œuvre

1. Publier le dépôt avec une licence open source explicite.
2. Documenter l'installation locale et l'auto-hébergement.
3. Conserver les replis locaux lorsque l'IA distante n'est pas disponible.
4. Afficher clairement sur l'accueil que le service est gratuit et communautaire.
5. Ne pas utiliser de bouton de paiement donnant accès à une fonctionnalité.
6. Protéger les CV, PDF, photos et candidatures par un contrôle d'accès applicatif ; les fichiers privés ne doivent pas être servis comme des fichiers statiques publics.
7. Ajouter une procédure de suppression de compte et de suppression des documents associés.

### Critères de sortie

- La licence et les licences des dépendances sont documentées.
- Une installation vierge est reproductible.
- Les documents d'un utilisateur ne sont pas accessibles à un autre utilisateur par modification d'URL.
- La suppression d'un compte supprime ou isole aussi ses fichiers et sauvegardes selon la politique publiée.
- Les fournisseurs externes utilisés par l'instance sont listés.

## Phase 2 — Observation et financement facultatif

### Objectif

Mesurer les coûts et l'usage avant de décider s'il faut créer une activité déclarée.

### Mise en œuvre

- Mesurer le nombre d'utilisateurs, le stockage, les appels IA et le temps de génération.
- Enregistrer les incidents et les demandes de support.
- Évaluer les coûts d'hébergement et de sauvegarde sans collecter le contenu des CV dans les logs.
- Si un soutien financier est proposé, le présenter comme facultatif et sans contrepartie.
- Conserver les relevés, justificatifs et conditions du prestataire.
- Ne pas présenter un montant comme un prix d'accès ou une formule.

### Point juridique

Un versement intitulé « don » peut être apprécié selon son contexte. Des versements réguliers, liés à l'usage ou associés à une contrepartie peuvent relever d'une activité rémunérée. Il faut vérifier la qualification fiscale et les obligations déclaratives en France avant d'accepter des revenus récurrents. Le recours à une plateforme de paiement ne supprime pas ces obligations.

Références de départ :

- [Service-Public — livre des recettes et registre des achats](https://entreprendre.service-public.gouv.fr/vosdroits/F23266)
- [CNIL — commencer une démarche RGPD](https://www.cnil.fr/fr/me-mettre-en-conformite/rgpd-par-ou-commencer)

## Phase 3 — Choix d'un cadre durable

Cette phase ne doit commencer que si les coûts, les contributions ou les demandes de service rendent nécessaire un financement régulier.

Options à étudier avec un professionnel :

| Option | Usage possible | Limite principale |
|---|---|---|
| Financement sans revenu | Le projet reste entièrement gratuit | Les coûts restent à la charge du mainteneur |
| Micro-entreprise | Vente d'un service hébergé ou prestations de support | Déclarations, facturation, fiscalité et obligations consommateur |
| Association | Projet d'intérêt collectif avec fonds affectés à l'objet | Les fonds ne peuvent pas servir à rémunérer personnellement le fondateur hors cadre adapté |
| Société | Service commercial structuré et équipe | Formalités et coûts plus importants |

Le passage à une offre payante devra être explicite : nouvelles conditions, prix, facturation, résiliation, gestion des impayés, information RGPD et séparation entre rôle d'administrateur et droit d'abonnement.

## Garde-fous à ne pas contourner

- Ne pas appeler « don » un paiement obligatoire ou nécessaire à l'accès.
- Ne pas promettre une disponibilité permanente de l'instance gratuite.
- Ne pas envoyer des CV à un fournisseur IA sans information et garanties adaptées.
- Ne pas exposer les fichiers sous `static/` par une URL prévisible.
- Ne pas publier de secrets, tokens ou données utilisateurs dans le dépôt.
- Faire valider le cadre fiscal et les conditions d'utilisation avant tout financement régulier.

