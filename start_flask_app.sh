#!/bin/bash

source /Users/display/PycharmProjects/jobs/venv/bin/activate

# Définir la variable d'environnement FLASK_APP avec le nom de votre application Flask
export FLASK_APP=flask_app.py

export FLASK_DEBUG=True

export FLASK_ENV=development
# export FLASK_ENV=production

# Définir le numéro de port sur lequel vous souhaitez exécuter l'application
export FLASK_RUN_PORT=8080

# Comment line to run on localhost only
export FLASK_RUN_HOST=0.0.0.0
# export FLASK_RUN_HOST=192.168.1.20

# Lancer l'application Flask en standalone
flask run
