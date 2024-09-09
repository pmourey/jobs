#### Site en ligne: [http://pmourey.pythonanywhere.com](https://pmourey.pythonanywhere.com/)

Pour bien démarrer:
- https://pythonbasics.org/flask-sqlalchemy/
- https://fr.w3docs.com/snippets/html/comment-ajouter-une-bordure-a-un-tableau-html.html
- https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/config/
- https://www.docstring.fr/blog/creer-une-todo-app-avec-flask/
- https://pypi.org/project/Flask-APScheduler/ 
- https://www.pythonanywhere.com/forums/topic/3627/#:~:text=You%20can%20enable%20it%20with,How%20do%20I%20enable%20threads%3F
- https://flask-fr.readthedocs.io/quickstart/

### Setup instructions
- Prérequis: Python (v3.10 conseillée) https://www.python.org/downloads/
- Cloner le dépôt sur la cible désirée (dans un environnement virtuel ou non)
- Importer les modules listés dans le fichier *requirements.txt*:
  - `pip install -r requirements.txt`
  - si erreur, mettre à jour le gestionnaire de module *pip*:
        *python -m pip install --upgrade pip*
- pour tout autre problème: contacter l'auteur ou chatGPT (en cas de non réponse)
- Et c'est aussi simple que cela! :-DDD

### Run instructions
- Prérequis:
  - nécessite un "Mot de passe d'application Gmail" pour fonctionner"
  - un serveur smtp supportant SSL
- Activation du scheduler (lancé au démarrage de la webapp):
  - *app.config['SCHEDULER'] = True*
- Modification de la périodicité d'envoi des mails:
  - *app.config['SCHEDULER_INTERVAL'] = 3600 * 24* (tous les jours)
- Lancement de l'application Flask (lire le manuel correspondant)

### Active bugs/Todos
- [ ] Création de compte possible même si e-mail inexistante
  - [ ] Ajouter une système de validation de création de compte par mail (comme déjà effectué sur celui de la récupération de mdp)
- [ ] bug gmail
  550 5.7.26 This mail has been blocked because the sender is unauthenticated. Gmail requires all senders to authenticate with either SPF or DKIM. Authentication results: DKIM = did not pass SPF [mourey.com] with ip: [209.85.220.41] = did not pass For instructions on setting up authentication, go to https://support.google.com/mail/answer/81126#authentication o33-20020a05600c512100b0040d5bbd5533sor3248472wms.13 - gsmtp
