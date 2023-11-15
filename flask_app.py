"""
Copyright © 2023 Philippe Mourey

This script provides CRUD features inside a Flask application for job's research follow-up and contact recruiters at monthly basis using a scheduler

"""
from __future__ import annotations
import atexit
import re
from typing import Match, Optional
from logging import basicConfig, DEBUG
import locale
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from itsdangerous import Serializer
from pytz import timezone
from flask import Flask, request, flash, url_for, redirect, render_template, session
from flask_sqlalchemy import SQLAlchemy
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy import DateTime, desc
from validators import url
from apscheduler.schedulers.background import BackgroundScheduler
import logging

from werkzeug.security import generate_password_hash, check_password_hash

from Controller import check, get_user_by_id, get_session_by_login, send_password_recovery_email
from Model import Job, User, db, Session
from tools.send_emails import send_email

from flask import render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, current_user, logout_user, login_required

app = Flask(__name__, static_folder='static', static_url_path='/static')
# Set the environment (development, production, etc.)
# Replace 'development' with the appropriate value for your environment
app.config.from_object('config.Config')
# app.config.from_pyfile(config_filename)

db.init_app(app)

toolbar = DebugToolbarExtension(app)


locale.setlocale(locale.LC_TIME, 'fr_FR')
basicConfig(level=DEBUG)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
# app.config['SECRET_KEY'] = 'fifa2022'
# app.config['SESSION_TYPE'] = 'filesystem'



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def welcome():
    user = None
    token = None
    if 'id' in session:
        user = get_user_by_id(session['id'])
        # Générer un jeton de récupération de mot de passe
        s = Serializer(app.config['SECRET_KEY'])
        token = s.dumps({'user_id': user.id})
        # Mettez à jour le modèle d'utilisateur avec le jeton et le délai d'expiration
        user.recovery_token = generate_password_hash(token, method='sha256')
        user.token_expiration = datetime.now(app.config['PARIS']) + timedelta(hours=24)
        db.session.commit()
    return render_template('index.html', session=session, user=user, token=token)

@app.route("/register", methods=['GET', 'POST'])
def register():
    # Logique d'enregistrement ici
    error = None
    if request.method == 'POST':
        if request.form['confirm_password'] != request.form['password']:
            # flash('Incorrect login credentials.', 'error')
            error = 'Password does not match! Please try again.'
        else:
            username: str = request.form['username']
            email: str = request.form['email']
            existing_user: User = User.query.filter_by(username=username).first()
            if existing_user:
                error = f'user {existing_user.username} already exists! Please choose another name.'
            elif not check(app.config['REGEX'], email):
                error = f'email {email} is invalid! Please check syntax.'
            else:
                user = User(username=username, password=request.form['password'], creation_date=datetime.now(app.config['PARIS']), email=email)
                # logging.warning("See this message in Flask Debug Toolbar!")
                db.session.add(user)
                db.session.commit()
                flash('Login was successfully created')
                return redirect(url_for('show_all'))
    return render_template('register.html', error=error)


@app.route("/login", methods=['GET', 'POST'])
def login():
    # Logique de connexion ici
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        # app.logger.debug(f'user = {user} - clear pwd = {request.form["password"]}')
        if user and check_password_hash(user.password, password=request.form['password']):
            session['id'] = user.id
            sess = Session(login=user.username, start=datetime.now(app.config['PARIS']))
            db.session.add(sess)
            db.session.commit()
            return redirect(url_for('welcome'))
        else:
            error = 'Incorrect login credentials. Please try again.'
            return render_template('login.html', error=error)
    return render_template('login.html', error=error)

@app.route("/change_password", methods=['GET', 'POST'])
def change_password():
    # Logique de connexion ici
    if 'id' in session:
        error = None
        if request.method == 'POST':
            user = get_user_by_id(session['id'])
            new_password: str = request.form["new_password"]
            confirm_new_password: str = request.form["confirm_new_password"]
            app.logger.debug(f'user (change pwd) = {user.username} - new pwd = {new_password} - confirm_new_pwd = {confirm_new_password}')
            if new_password == confirm_new_password:
                user.password = generate_password_hash(new_password, method='sha256')
                db.session.add(user)
                db.session.commit()
                flash('Password was successfully changed!')
                return redirect(url_for('welcome'))
            else:
                error = 'Passwords does not match! Please try again.'
        return render_template('reset_password.html', error=error)
    else:
        return redirect(url_for('login.html'))

@app.route('/request_reset_password', methods=['GET', 'POST'])
def request_reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            # Générer un jeton de récupération de mot de passe
            s = Serializer(app.config['SECRET_KEY'])
            token = s.dumps({'user_id': user.id})

            # Mettez à jour le modèle d'utilisateur avec le jeton et le délai d'expiration
            user.recovery_token = generate_password_hash(token, method='sha256')
            user.token_expiration = datetime.now(app.config['PARIS']) + timedelta(minutes=10)

            db.session.commit()

            # Envoyer le lien de récupération par e-mail (vous devez implémenter cette partie)
            # Vous pouvez utiliser un package comme Flask-Mail pour envoyer des e-mails.

            flash('Un e-mail de récupération de mot de passe a été envoyé.', 'success')
            reset_link = url_for('reset_password', token=token, _external=True)
            send_password_recovery_email(app=app, reset_link=reset_link, user=user, author=app.config['GMAIL_FULLNAME'], cv_resume=app.config['CV_RESUME'])
            return redirect(url_for('login'))

        flash('Aucun utilisateur trouvé avec cet e-mail.', 'error')

    return render_template('request_reset_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    error: str = None
    # Vérifier si le jeton est valide
    s = Serializer(app.config['SECRET_KEY'])
    try:
        data = s.loads(token)
    except:
        flash('Le lien de réinitialisation de mot de passe est invalide ou a expiré.')
        return redirect(url_for('login'))

    user = User.query.get(data['user_id'])
    app.logger.debug(f'reset password user {user.username} - data = {data} \n - token = {token}')

    if request.method == 'POST':

        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')

        if new_password == confirm_new_password:
            # Mettre à jour le mot de passe de l'utilisateur
            user.password = generate_password_hash(new_password, method='sha256')

            # Réinitialiser le champ de récupération de mot de passe
            user.recovery_token = None
            user.token_expiration = None

            db.session.commit()

            flash('Le mot de passe a été réinitialisé avec succès.', 'success')
            return redirect(url_for('login'))
        else:
            error = 'Les mots de passe ne correspondent pas.'

    return render_template('reset_password.html', error=error, token=token)

@app.route("/logout")
def logout():
    user = get_user_by_id(session['id'])
    sess = get_session_by_login(username=user.username)
    if sess is not None:
        sess.end = datetime.now(app.config['PARIS'])
        db.session.commit()
    logout_user()
    # remove the username from the session if it's there
    session.pop('id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/accounts')
def show_accounts():
    # app.logger.debug("PROUT")
    if 'id' in session:
        user = get_user_by_id(session['id'])
        if user.is_admin:
            # Faire quelque chose avec l'ID de l'utilisateur, par exemple, récupérer ses informations depuis la base de données
            # Reverse order query
            accounts = User.query.order_by(desc(User.id)).all()
            return render_template('accounts.html', accounts=accounts, user=user)
    else:
        return redirect(url_for('login'))

@app.route('/sessions')
def show_sessions():
    # app.logger.debug("PROUT")
    if 'id' in session:
        user = get_user_by_id(session['id'])
        if user.is_admin:
            # Faire quelque chose avec l'ID de l'utilisateur, par exemple, récupérer ses informations depuis la base de données
            # Reverse order query
            sessions = Session.query.filter(Session.end.is_(None)).order_by(desc(Session.id)).all()
            return render_template('sessions.html', sessions=sessions)
    else:
        return redirect(url_for('login'))

@app.route('/suivi')
def show_all():
    if 'id' in session:
        user_id = session['id']
        # Faire quelque chose avec l'ID de l'utilisateur, par exemple, récupérer ses informations depuis la base de données
        app.logger.debug('This is a debug message.')
        # Reverse order query
        jobs = Job.query.filter(Job.active).order_by(desc(Job.applicationDate)).all()
        user = get_user_by_id(user_id)
        return render_template('candidatures.html', jobs=jobs, user=user)
    else:
        return redirect(url_for('login'))

@app.route('/new/', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        email: str = request.form['email']
        if not (request.form['name'] and request.form['url'] and request.form['company']):
            flash('Please enter all the fields', 'error')
        elif email and not check(app.config['REGEX'], email):
            flash(f'Invalid E-Mail {email}!', 'error')
        else:
            job = Job(name=request.form['name'], url=request.form['url'],
                      zipCode=request.form['zipCode'], company=request.form['company'],
                      contact=request.form['contact'], date=datetime.now(app.config['PARIS']), email=email, user_id=session['id'])
            # logging.warning("See this message in Flask Debug Toolbar!")
            job.is_capture = job.capture_exists()
            db.session.add(job)
            db.session.commit()
            flash('Record was successfully added')
    return redirect(url_for('show_all'))
    # return render_template('candidatures.html')


@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    app.logger.debug(f'Delete job #{id}')
    if request.method == 'GET':
        job = Job.query.get_or_404(id)
        app.logger.debug(f'Job debug: {job}')
        # db.session.delete(job)
        job.active = False
        db.session.commit()
        flash(f'Job offer \"{job.name}\" from  \"{job.contact}\" was disabled!')
        return redirect(url_for('show_all'))

@app.route('/delete_account/<int:id>', methods=['GET', 'POST'])
def delete_account(id):
    app.logger.debug(f'Delete user #{id}')
    if request.method == 'GET':
        user = User.query.get_or_404(id)
        app.logger.debug(f'User debug: {user}')
        db.session.delete(user)
        db.session.commit()
        flash(f'User \"{user.username}\" has been deleted!')
        return redirect(url_for('show_accounts'))

@app.route('/update_account/<int:id>', methods=['GET', 'POST'])
def update_account(id):
    user: User = User.query.get_or_404(id)
    # app.logger.debug(f'User debug: {user}')
    if request.method == 'POST':
        roles = ['Administrateur', 'Editeur', 'Lecteur']
        user.role = roles.index(request.form.get('role'))
        db.session.commit()
        flash('Record was successfully updated')
        return redirect(url_for('show_accounts'))
    else:
        return render_template('update_account.html', user=user)

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    job: Job = Job.query.get_or_404(id)
    if request.method == 'POST':
        job.name = request.form.get('name')
        job.url = request.form.get('url')
        job.zipCode = request.form.get('zipCode')
        job.company = request.form.get('company')
        job.contact = request.form.get('contact')
        job.email = request.form.get('email')
        application_date: str = request.form.get('applicationDate')
        app.logger.debug(f'application_date: {application_date}')
        job.applicationDate = datetime.strptime(application_date, '%Y-%m-%d') if application_date else None
        relaunch_date: str = request.form.get('relaunchDate')
        job.relaunchDate = datetime.strptime(relaunch_date, '%Y-%m-%d') if relaunch_date else None
        refusal_date: str = request.form.get('refusalDate')
        job.refusalDate = datetime.strptime(refusal_date, '%Y-%m-%d') if refusal_date else None
        db.session.commit()
        flash('Record was successfully updated')
        return redirect(url_for('show_all'))
    else:
        return render_template('update.html', job=job)


@app.before_request
def create_tables():
    db.create_all()


@app.before_request
def create_captures_dir():
    directory_path = f'{os.path.dirname(__file__)}/static/images'
    if not os.path.exists(directory_path):
        try:
            os.mkdir(directory_path)
            print(f"Directory {directory_path} created successfully.")
        except Exception as e:
            print(f"Error creating directory: {e}")



# if app.config['SCHEDULER']:
#     app.logger.debug(app.config['SCHEDULER'])
#     scheduler = BackgroundScheduler()
#     scheduler.add_job(func=send_reminders, trigger="interval", seconds=app.config['SCHEDULER_INTERVAL'])
#     scheduler.start()
#
#     # Shut down the scheduler when exiting the app
#     atexit.register(lambda: scheduler.shutdown())

# app.run()
# toolbar.init_app(app)
# app.run(debug=True, use_debugger=True, use_reloader=False)
