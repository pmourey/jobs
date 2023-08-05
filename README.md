Pour bien démarrer:
- https://www.kaherecode.com/tutorial/demarrer-avec-flask-un-micro-framework-python
- https://pythonbasics.org/flask-sqlalchemy/
- https://fr.w3docs.com/snippets/html/comment-ajouter-une-bordure-a-un-tableau-html.html
- https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/config/
- https://www.docstring.fr/blog/creer-une-todo-app-avec-flask/
- https://pypi.org/project/Flask-APScheduler/ 
- https://www.pythonanywhere.com/forums/topic/3627/#:~:text=You%20can%20enable%20it%20with,How%20do%20I%20enable%20threads%3F

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
