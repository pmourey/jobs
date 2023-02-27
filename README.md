Pour faire joujou en ligne...
- http://philrg.pythonanywhere.com/
- http://pmourey.pythonanywhere.com/

Pour bien démarrer:
- https://www.kaherecode.com/tutorial/demarrer-avec-flask-un-micro-framework-python
- https://pythonbasics.org/flask-sqlalchemy/
- https://fr.w3docs.com/snippets/html/comment-ajouter-une-bordure-a-un-tableau-html.html
- https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/config/

### Setup instructions
- Installer les fichiers suivants sur la racine de l'application Flask créé sur Pythonanywhere:
  - requirements.txt (liste des modules requis pour le fonctionnement de SQLAlchemy et Flask)
  - flask_app.py (code de lancement de l'application Flask)
  - templates/new.html (template Jinja2)
  - templates/show_all.html (template Jinja2)
  
  - J'ai eu une erreur sur la console Bash du provider, lors de l'installation d'un module (problème de dépendance):
  
  `ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
  gevent 21.12.0 requires greenlet<2.0,>=1.1.0; platform_python_implementation == "CPython", but you have greenlet 2.0.1 which is incompatible.`

    Je l'avais déjà eu sur mon IMac. Il faut upgrader la version de pip par la commande suivante, et réinstaller les modules pour faire disparaître le message:

    `python -m pip install --upgrade pip

    `pip install -r requirements.txt`

    Et c'est aussi simple que cela!