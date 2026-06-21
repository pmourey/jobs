# Notes sur l'API France Travail et son implémentation

Ce document local décrit :

- où trouver la documentation officielle de l'API France Travail (FT)
- comment l'API a été intégrée dans ce projet Flask
- investigations sur les différences observées entre le site Web FT (frontend) et les résultats renvoyés par l'API
- causes probables pour l'absence de certaines données (entreprise, salaire) et l'absence du "mode de travail"

Date : 2026-06-20

---

## 1) Documentation officielle

- Portail développeur France Travail (ex-Apprentissage / Pôle Emploi) :
  - URL principale (peut évoluer) : https://developers.francetravail.gouv.fr/  
  - Documentation des endpoints d'offres : chercher les sections "offers", "recruitment" ou "search" dans le portail.
  - Spécifications OAuth / client credentials (FT_CLIENT_ID / FT_CLIENT_SECRET) si mode réel.

Remarque : selon la période, l'API peut se trouver sur une sous-plateforme ou dans la doc de l'opérateur qui opère la recherche d'offres (France Travail, Pôle Emploi, ou agrégateurs). Si les URLs ci‑dessus ne sont plus valides, rechercher "France Travail API offres développeurs".

## 2) Où l'API est implémentée dans ce dépôt

- Fichiers clefs à consulter :
  - `tools/france_travail.py` : wrapper d'appel à l'API France Travail — logique d'obtention du token, construction des requêtes et parsing de la réponse.
  - `flask_app.py` : endpoints exposés `/france_travail` (ou similaires) qui orchestrent les recherches et stockent les `FtSearch` en base.
  - `Model.py` : schéma de la table `FtSearch` et méthodes getter/setter liées aux offres retournées.

- Variables de configuration attendues (dans `config.py` / `config_template.py`) :
  - `FT_CLIENT_ID`, `FT_CLIENT_SECRET` — identifiants OAuth (client credentials)
  - éventuellement `FT_BASE_URL`, `FT_SCOPE` ou autres constantes pour l'URL et scopes.

## 3) Comportement observé : moins d'offres via l'API que via le frontend

Observations rapportées :

- Quand vous utilisez l'interface Web France Travail (avec votre compte), vous obtenez plus d'offres pour les mêmes critères que celles retournées par notre endpoint serveur (via `tools/france_travail.py`).

Causes possibles et vérifications à effectuer :

1. Authentification / permissions :
   - Le frontend Web authentifié utilise un utilisateur connecté (session, cookies) avec des droits ou du contexte géographique/compte qui peuvent élargir les résultats (ex : offres masquées en mode anonyme).
   - L'API appelée depuis le serveur utilise des credentials d'application (client credentials). Vérifier si l'API distingue les scopes/permissions entre user-token et client-token — certaines offres peuvent être renvoyées uniquement pour des utilisateurs authentifiés.

2. Paramètres de requête et filtres :
   - Le frontend peut implicitement ajouter des filtres (rayon, ponderation, tri, préférences) ou enrichir la requête (normalisation d'intitulé, expansion de mots-clés, suggestions) qui ne sont pas envoyés par notre wrapper.
   - Vérifier les paramètres envoyés par le frontend (via onglet Réseau du navigateur) et comparer avec la payload construite dans `tools/france_travail.py`.

3. Pagination / limite de résultats :
   - L'API peut limiter le nombre d'offres par page / par requête (ex : 20, 50). Le frontend peut effectuer plusieurs requêtes en arrière-plan et agréger les résultats.
   - Vérifier `size`, `from`, `page` ou paramètres analogues envoyés par notre code.

4. Localisation / géolocalisation / préférences utilisateur :
   - Le site Web peut utiliser la géolocalisation du navigateur, l'historique du compte ou des préférences (zones favorisées) pour élargir/réordonner les résultats.

5. Enrichissements côté frontend :
   - Le frontend pourrait dédupliquer/joindre plusieurs sources (aggrégation) ou effectuer des appels supplémentaires à d'autres endpoints (par exemple, appels pour les offres masquées ou pour récupérer des offres archivées). Notre intégration peut appeler uniquement l'endpoint de base.

6. Environnement d'API : sandbox vs production :
   - Vérifier que `FT_BASE_URL` ou les credentials pointent bien vers l'environnement production et non une sandbox restreinte.

Action recommandée :
 - Capturer une requête réseau (devtools) depuis le frontend pour un même jeu de critères, exporter la requête complète (headers, payload). Comparer avec la requête construite par `tools/france_travail.py`.
 - Vérifier les headers d'auth (Authorization, Cookie) et les paramètres query/body (aggs, sources, fields, size, from).

## 4) Pourquoi certaines offres n'ont pas d'information entreprise / salaire

Causes probables :

1. Données manquantes côté source :
   - L'API peut renvoyer des offres où les champs `employer`, `company`, `salary` ne sont pas renseignés par l'employeur ou le diffuseur. C'est fréquent : le salaire est souvent manquant dans les annonces.

2. Champs optionnels / source multiple :
   - Selon la source de l'offre (Pôle Emploi, jobboards partenaires, import CSV), le schéma n'est pas homogène. Certains partenaires ne transmettent pas l'ensemble des métadonnées.

3. Champs filtrés par `fields` ou `source` dans la requête :
   - L'API supporte souvent un paramètre `fields` (ou `_source`) pour limiter les champs retournés. Si notre wrapper demande un sous-ensemble, certains champs sont absents.

4. Politique de confidentialité / anonymisation :
   - Certaines offres peuvent être anonymisées (pas d'identité d'entreprise) volontairement par le diffuseur.

5. Post-traitement côté serveur :
   - Vérifier `tools/france_travail.py` et le code de parsing : il se peut que le mapping entre le JSON de l'API et notre modèle supprime ou ignore certains champs (naming mismatch : `employer` vs `employeur` vs `company_name`).

Action recommandée :
 - Loguer la réponse brute (JSON complet) renvoyée par l'API pour quelques offres manquantes et inspecter si le champ existe mais sous un autre nom, ou s'il est réellement absent/null.
 - Comparer avec la requête du frontend : le frontend peut faire un appel supplémentaire pour récupérer la fiche complète d'une offre (endpoint /offers/{id}) qui contient l'entreprise et le salaire.

## 5) Pourquoi le "mode de travail" (présentiel / hybride / télétravail) n'est jamais renvoyé

Explications possibles :

1. Champ non exposé par l'API ou champ récent :
   - Le mode de travail peut être un champ récent / non standardisé et donc pas inclus dans la version d'API que vous utilisez.

2. Champ stocké dans un autre endpoint :
   - Certaines APIs séparèrent la recherche rapide (liste d'offres) et le détail d'offre. Le champ "mode de travail" peut être disponible uniquement dans l'endpoint de détail (GET /offers/{id}). Si vous n'appelez que l'endpoint de recherche, il peut manquer.

3. Normalisation / vocabulaire différent :
   - Le champ peut exister mais sous un nom différent (`work_mode`, `remote`, `teletravail`, `position_type`, `workplaceType`). Si notre mapping n'en tient pas compte, on le considérera comme absent.

4. Filtrage des champs côté requête (voir 4.3) :
   - Si la requête limite les champs, le mode de travail ne sera pas retourné.

Action recommandée :
 - Vérifier dans `tools/france_travail.py` si on utilise un paramètre limitant `_source`/`fields`. Si oui, retirer la limitation ou ajouter explicitement le champ correspondant.
 - Pour une offre concrète vue sur le frontend : effectuer un appel direct au endpoint de détail (via curl ou navigateur) pour vérifier si le champ existe dans la réponse détaillée.
 - Inspecter la documentation officielle pour la dénomination et le chemin du champ (ex: `workplace`, `workConditions`, `workPlaceType`).

## 6) Checklist de corrections / tâches à mener

1. Capturer une requête réseau complète depuis le frontend pour une recherche identique (Headers + payload).
2. Comparer la requête frontend avec `tools/france_travail.py` (payload, headers, pagination, fields).
3. Loguer et stocker la réponse brute JSON côté serveur pour plusieurs offres manquantes (débug temporaire) :
   - Ajouter logs dans `tools/france_travail.py` (ou débog mode) pour écrire la réponse dans `instance/` ou `flask_server.log`.
4. Vérifier si l'environnement FT (sandbox vs prod) est le même que celui du frontend.
5. Vérifier si l'API supporte un endpoint de détail d'offre, et appeler cet endpoint pour les IDs manquants.
6. Mettre à jour le mapping dans `tools/france_travail.py` pour gérer les alias de champs (company / employer / entreprise, remote / telework / workplaceType, salary / remuneration).
7. Ajouter tests unitaires dans `test/` qui utilisent des responses fixtures (dump JSON) et valident que le parsing récupère company, salary et work_mode si présents.

## 7) Notes pratiques / risques

- Ne pas afficher en clair les `FT_CLIENT_SECRET` dans les logs ; loguer seulement l'ID de requête ou une anonymisation.
- Si vous modifiez la pagination / rate limit, attention aux quotas API.
- Garder les fallbacks pour tests hors réseau (mock responses) comme déjà pratiqué pour les fonctions IA.

---

Fichiers à consulter en priorité :

- `tools/france_travail.py`
- `flask_app.py` (endpoints `/france_travail` / pages FT)
- `Model.py` (classe `FtSearch`)

Si vous voulez, je peux :

1) ouvrir `tools/france_travail.py`, ajouter du logging temporaire et préparer un script/curl pour reproduire la requête frontend ;
2) ajouter un test fixture et un test unitaire qui montre le cas manquant (company/salary/work_mode) et corriger le mapping.

Dites-moi quelle action vous préférez que j'exécute en suivant (1) ou (2) ou autre.

