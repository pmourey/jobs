- [x] Re-factorisation du code pour séparer les couches (Model/Vue/Contrôleur)
- [x] Création de l'enregistrement utilisateur et authentification (rôle par défaut: lecteur)
  - [x] Gestion du hash du mot de passe (mdp hashé en bdd)
  - [x] Modification du mot de passe
  - [x] Réinitialisation de mot de passe oublié (envoi par mail)
  - [x] Confirmation de création de compte (envoi par mail)
  - [x] Activation protection SPF (contre SPAM) sur champ TXT DNS Gandi (pour autorisation envoi mail vers domaines externes)
  - [ ] Re-factoriser un système d'accès aux routes pour un user donné
- [ ] Gestion des rôles (administrateur/éditeur/lecteur) pour les accès CRUD
  - [x] Implémentation du rôle Admin et filtrage des vues
  - [x] Attribution des rôles pour l'administrateur du site (rajout des droits)
  - [ ] Gestion du mode éditeur (et owner de l'offre)
- [x] Création d'une table d'historisation des connections utilisateur