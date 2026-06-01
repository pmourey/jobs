"""
Copyright © 2023 Philippe Mourey

This script provides CRUD features inside a Flask application for job's research follow-up and contact recruiters at monthly basis using a scheduler

"""
from __future__ import annotations

import atexit
import locale
import logging
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session

# Ensure NO_PROXY is set (some environments use lowercase 'no_proxy') so requests bypasses
# the corporate proxy for France Travail domains when the variable was exported locally.
if not os.environ.get('NO_PROXY') and os.environ.get('no_proxy'):
    os.environ['NO_PROXY'] = os.environ.get('no_proxy')
os.environ.setdefault('NO_PROXY', 'entreprise.francetravail.fr,api.francetravail.io')
import re
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from logging import DEBUG, basicConfig
from pathlib import Path
from socket import socket
from time import sleep
from typing import Match, Optional

import pytz
from _socket import gethostbyname
from apscheduler.schedulers.background import BackgroundScheduler
from dateutil.relativedelta import relativedelta
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   send_file, session, url_for)
from flask_debugtoolbar import DebugToolbarExtension
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import Serializer, URLSafeSerializer
from pytz import timezone
from sqlalchemy import DateTime, case, desc, func
from user_agents import parse
from user_agents.parsers import UserAgent
from validators import url
from werkzeug.security import generate_password_hash  # , check_password_hash

from Controller import (check, check_password_and_upgrade,
                        get_session_by_login, get_user_by_id,
                        handle_file_upload, send_confirmation_email,
                        send_password_recovery_email)
from Model import AppSetting, FtSearch, Job, Session, User, db
from tools.cv_tools import (build_cv_pdf_filename,
                            generate_tailored_cv_pdf_bytes,
                            get_ai_cover_letter_text, get_ai_cv_suggestions,
                            load_cv_data)
from tools.document_tools import (build_cover_letter_pdf_filename,
                                  generate_cover_letter_pdf_bytes,
                                  resolve_cover_letter_template_path)
from tools.france_travail import (ATS_KEYWORDS_PROFILE, CONTRACT_TYPES,
                                  DEPARTMENTS, WORK_MODES, search_auto_from_cv,
                                  search_offers)
from tools.send_emails import send_email

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

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

""" decorators """


def is_connected(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # app.logger.debug(f'is_connected: session = {session}')
        if 'login_id' not in session:
            error = 'Restricted access! Please authenticate.'
            # Si requête AJAX / JSON, retourner 401 JSON utile au JS
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                from flask import jsonify
                return jsonify({ 'error': error }), 401
            return render_template('login.html', error=error)
            # return redirect(url_for('login.html'))  # Remplacez 'login.html' par l'URL de votre page de connexion
        return func(*args, **kwargs)

    return wrapper

def is_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_user_by_id(session['login_id'])
        if not user.is_admin:
            error = 'Insufficient privileges for this operation! Please contact administrator...'
            # Si requête AJAX / JSON, retourner 403 JSON utile au JS
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                from flask import jsonify
                return jsonify({ 'error': error }), 403
            return render_template('login.html', error=error)
        return func(*args, **kwargs)
    return wrapper

def is_editor_or_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_user_by_id(session['login_id'])
        if not (user.is_editor or user.is_admin):
            error = 'Insufficient privileges for this operation! Please contact administrator...'
            return render_template('login.html', error=error)
        return func(*args, **kwargs)
    return wrapper

def get_client_ip():
    # Check headers in order of reliability
    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist("X-Forwarded-For")[0]
    elif request.headers.get("X-Real-IP"):
        client_ip = request.headers.get("X-Real-IP")
    elif request.headers.get("CF-Connecting-IP"):    # Cloudflare
        client_ip = request.headers.get("CF-Connecting-IP")
    else:
        client_ip = request.remote_addr
    return client_ip

@app.route('/get_ip')
def get_ip():
    # Obtenir l'adresse IP du client
    # client_ip = request.remote_addr
    # app.logger.debug(f'old client_ip = {client_ip}')
    client_ip = get_client_ip()
    app.logger.debug(f'new client_ip = {client_ip}')

    # Obtenir le nom d'hôte du serveur
    server_hostname = request.host.split(':')[0]

    # Résoudre le nom d'hôte en adresse IP
    server_ip = gethostbyname(server_hostname)

    return f"Adresse IP du client : {client_ip}\nAdresse IP du serveur : {server_ip}"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def welcome():
    user = None
    token = None
    if 'login_id' in session:
        user = get_user_by_id(session['login_id'])
        # Générer un jeton de récupération de mot de passe
        s = Serializer(app.config['SECRET_KEY'])
        token = s.dumps({'user_id': user.id})
        # Mettez à jour le modèle d'utilisateur avec le jeton et le délai d'expiration
        # user.recovery_token = generate_password_hash(token, method='sha256')
        user.recovery_token = generate_password_hash(token)
        user.token_expiration = datetime.now() + timedelta(hours=24)
        db.session.commit()
    else:
        # client_ip = request.remote_addr
        client_ip = get_client_ip()
        user_agent_string = request.headers.get('User-Agent')
        user_agent: UserAgent = parse(user_agent_string)
        browser_info = f"Family = {user_agent.browser.family}, Version = {user_agent.browser.version_string}"
        app.logger.debug(f"Client IP: {client_ip}, Browser: ({browser_info})")
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
            existing_email: User = User.query.filter_by(email=email).first()
            if existing_user:
                error = f'user {existing_user.username} already exists! Please choose another name.'
            elif existing_email:
                error = f'email {existing_email.email} already exists! Please choose another email.'
            elif not check(app.config['REGEX'], email):
                error = f'email {email} is invalid! Please check syntax.'
            else:
                user = User(username=username, password=request.form['password'],
                            creation_date=datetime.now(), email=email)
                # logging.warning("See this message in Flask Debug Toolbar!")
                db.session.add(user)
                db.session.commit()
                s = Serializer(app.config['SECRET_KEY'])
                # s = URLSafeSerializer('SECRET_KEY')
                token = s.dumps({'user_id': user.id})

                # Mettez à jour le modèle d'utilisateur avec le jeton et le délai d'expiration
                # user.recovery_token = generate_password_hash(token, method='sha256')
                user.recovery_token = generate_password_hash(token)
                user.token_expiration = datetime.now() + timedelta(minutes=10)
                # app.logger.debug(f'time zone info: {user.token_expiration.tzinfo}')

                db.session.commit()

                # Envoyer un e-mail de confirmation d'inscription

                flash('Un e-mail de demande de confirmation d\'inscription a été envoyé!', 'success')
                confirm_link = url_for('validate_email', token=token, _external=True)
                send_confirmation_email(app=app, confirm_link=confirm_link, user=user,
                                        author=app.config['GMAIL_FULLNAME'], cv_resume=app.config['CV_RESUME'])
                return redirect(url_for('register'))

    return render_template('register.html', error=error)


@app.route("/login", methods=['GET', 'POST'])
def login():
    # Logique de connexion ici
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        app.logger.debug(f'user = {user} - password: {user.password} - clear pwd = {request.form["password"]}')
        if user and check_password_and_upgrade(user, password=request.form['password']):
            if user.validated:
                session['login_id'] = user.id
                app.logger.debug(f'user (login) = {user.username} - id = {user.id} - session: {session}')
                # client_ip = request.remote_addr
                client_ip = get_client_ip()
                user_agent_string = request.headers.get('User-Agent')
                user_agent: UserAgent = parse(user_agent_string)
                sess = Session(login_id=user.id, start=datetime.now(), client_ip=client_ip,
                               browser_family=user_agent.browser.family,
                               browser_version=user_agent.browser.version_string)
                db.session.add(sess)
                db.session.commit()
                return redirect(url_for('welcome'))
            else:
                error = 'Your account is not yet validated! Please check your email for the confirmation link.'
                return render_template('login.html', error=error)
        else:
            error = 'Incorrect login credentials. Please try again.'
            return render_template('login.html', error=error)
    return render_template('login.html', error=error)


@app.route("/change_password", methods=['GET', 'POST'])
@is_connected
def change_password():
    error = None
    if request.method == 'POST':
        user = get_user_by_id(session['login_id'])
        new_password: str = request.form["new_password"]
        confirm_new_password: str = request.form["confirm_new_password"]
        app.logger.debug(
            f'user (change pwd) = {user.username} - new pwd = {new_password} - confirm new_pwd = {confirm_new_password}')
        if new_password == confirm_new_password:
            # user.password = generate_password_hash(new_password, method='sha256')
            user.password = generate_password_hash(new_password)
            db.session.add(user)
            db.session.commit()
            flash('Password was successfully changed!')
            return redirect(url_for('welcome'))
        else:
            error = 'Passwords does not match! Please try again.'
    return render_template('reset_password.html', error=error)


@app.route('/request_reset_password', methods=['GET', 'POST'])
def request_reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email.lower()).first()
        if user:
            # Générer un jeton de récupération de mot de passe
            s = Serializer(app.config['SECRET_KEY'])
            token = s.dumps({'user_id': user.id})

            # Mettez à jour le modèle d'utilisateur avec le jeton et le délai d'expiration
            # user.recovery_token = generate_password_hash(token, method='sha256')
            user.recovery_token = generate_password_hash(token)
            user.token_expiration = datetime.now() + timedelta(minutes=10)

            db.session.commit()

            # Envoyer le lien de récupération par e-mail (vous devez implémenter cette partie)
            # Vous pouvez utiliser un package comme Flask-Mail pour envoyer des e-mails.

            flash('Un e-mail de récupération de mot de passe a été envoyé.', 'success')
            reset_link = url_for('reset_password', token=token, _external=True)
            send_password_recovery_email(app=app, reset_link=reset_link, user=user, author=app.config['GMAIL_FULLNAME'],
                                         cv_resume=app.config['CV_RESUME'])
            return redirect(url_for('login'))

        flash('Aucun utilisateur trouvé avec cet e-mail.', 'error')

    return render_template('request_reset_password.html')


@app.route('/validate_email/<token>', methods=['GET', 'POST'])
def validate_email(token):
    error: str = None
    # Vérifier si le jeton est valide
    s = Serializer(app.config['SECRET_KEY'])
    try:
        data = s.loads(token)
        user = User.query.get_or_404(data['user_id'])
        # Calculate the time difference
        remaining_minutes = int((user.token_expiration - datetime.now()).total_seconds() / 60)
        app.logger.debug(f'remaining minutes: {remaining_minutes}')
        if remaining_minutes <= 0:
            raise Exception
    except Exception as e:
        app.logger.debug(e)
        flash('Le lien de confirmation d\'inscription est invalide ou a expiré.')
        user = User.query.get_or_404(data.get('user_id'))
        if user:
            db.session.delete(user)
            db.session.commit()
        return redirect(url_for('login'))

    user = User.query.get(data['user_id'])

    # Mettre à jour le champ de confirmation d'inscription de l'utilisateur
    user.validated = True

    # Réinitialiser le champ de récupération de mot de passe
    user.recovery_token = None
    user.token_expiration = None

    db.session.commit()

    flash('Votre compte a été confirmé avec succès.', 'success')
    return redirect(url_for('login'))


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    error: str = None
    # Vérifier si le jeton est valide
    s = Serializer(app.config['SECRET_KEY'])
    try:
        data = s.loads(token)
        user = User.query.get_or_404(data['user_id'])
        # Calculate the time difference
        remaining_minutes = int((user.token_expiration - datetime.now()).total_seconds() / 60)
        app.logger.debug(f'remaining minutes: {remaining_minutes}')
        if remaining_minutes <= 0:
            raise Exception
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
            # user.password = generate_password_hash(new_password, method='sha256')
            user.password = generate_password_hash(new_password)

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
@is_connected
def logout():
    user = get_user_by_id(session['login_id'])
    sess = get_session_by_login(username=user.username)
    if sess is not None:
        sess.end = datetime.now()
        db.session.commit()
    logout_user()
    # clear all session data including cookies
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/accounts')
@is_connected
@is_admin
def show_accounts():
    user = get_user_by_id(session['login_id'])
    # Query users together with their session counts and sort by count desc
    count_expr = func.count(Session.id)
    results = db.session.query(User, count_expr.label('connection_count')).outerjoin(Session, Session.login_id == User.id).group_by(User.id).order_by(desc(count_expr)).all()
    accounts = []
    for user_obj, conn_count in results:
        # attach the count and last session
        user_obj.connection_count = conn_count
        user_obj.last_session = Session.query.filter_by(login_id=user_obj.id).order_by(desc(Session.start)).first()
        accounts.append(user_obj)
    return render_template('accounts.html', accounts=accounts, user=user)


@app.route('/delete_session/<int:id>', methods=['POST'])
@is_connected
@is_admin
def delete_session(id):
    session_obj = Session.query.get_or_404(id)
    current_user_id = session['login_id']
    if session_obj.end is None:
        if session_obj.login_id == current_user_id:
            return jsonify({ 'error': 'Cannot close your own active session' }), 403
        # Close active session of another user
        session_obj.end = datetime.now()
        db.session.commit()
    else:
        # Delete closed session permanently (any user)
        db.session.delete(session_obj)
        db.session.commit()
    return '', 200


@app.route('/delete_sessions', methods=['GET', 'POST'])
@is_connected
@is_admin
def delete_sessions():
    """Supprime (marque end=now) plusieurs sessions à la fois.
    - GET : renvoie un message de diagnostic (utilisé pour vérifier que la route est bien active).
    - POST : attend un JSON { "ids": [1,2,3] } et met à jour les sessions.
    """
    app.logger.debug(f"delete_sessions called: method={request.method} path={request.path}")
    try:
        raw = request.get_data(as_text=True)
    except Exception:
        raw = None
    app.logger.debug(f"delete_sessions raw payload: {raw}")

    if request.method == 'GET':
        return jsonify({ 'message': 'Endpoint /delete_sessions disponible', 'method': 'GET' }), 200

    # POST handler
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({ 'error': 'Invalid JSON' }), 400

    if not data or 'ids' not in data:
        return jsonify({ 'error': 'Missing ids list' }), 400

    ids = data.get('ids')
    if not isinstance(ids, list) or any(not isinstance(i, int) for i in ids):
        return jsonify({ 'error': 'ids must be a list of integers' }), 400

    # Query all sessions matching provided ids
    sessions_to_close = Session.query.filter(Session.id.in_(ids)).all()
    print(f"DEBUG delete_sessions: found {len(sessions_to_close)} sessions for ids {ids}")
    now = datetime.now()
    closed_ids = []
    deleted_ids = []
    current_user_id = session['login_id']
    for sess in sessions_to_close:
        print(f"DEBUG Processing session {sess.id}, end={sess.end}, login_id={sess.login_id}")
        if sess.end is None:
            if sess.login_id == current_user_id:
                print(f"DEBUG Skipping own active session {sess.id}")
                continue  # Skip closing own session
            sess.end = now
            closed_ids.append(sess.id)
        else:
            db.session.delete(sess)
            deleted_ids.append(sess.id)
    try:
        db.session.commit()
        print(f"DEBUG Committed successfully: closed {closed_ids}, deleted {deleted_ids}")
    except Exception as e:
        print(f"DEBUG Commit failed: {e}")
        db.session.rollback()
        return jsonify({ 'error': 'Commit failed' }), 500
    return jsonify({ 'closed': closed_ids, 'deleted': deleted_ids }), 200


@app.route('/sessions')
@is_connected
@is_admin
def show_sessions():
    # Reverse order query
    sessions = Session.query.filter(Session.end.is_(None)).order_by(desc(Session.id)).all()
    user = get_user_by_id(session['login_id'])
    return render_template('sessions.html', sessions=sessions, user=user)


@app.route('/closed_sessions')
@is_connected
@is_admin
def show_closed_sessions():
    username_filter = request.args.get('username', '')
    query = Session.query.filter(Session.end.is_not(None))
    if username_filter:
        query = query.join(User).filter(User.username == username_filter)
    sessions = query.order_by(desc(Session.end)).all()
    users = db.session.query(User.username).distinct().order_by(User.username).all()
    return render_template('closed_sessions.html', sessions=sessions, username_filter=username_filter, users=users)


@app.route('/suivi')
@is_connected
def show_all():
    user_id = session['login_id']
    app.logger.debug('This is a debug message.')
    jobs = Job.query.all()
    def most_recent_date(job):
        dates = [d for d in (job.relaunchDate, job.applicationDate) if d]
        if not dates:
            return datetime.min
        return max(dates)

    jobs.sort(key=most_recent_date, reverse=True)
    for j in jobs:
        rd = most_recent_date(j)
        try:
            j.recent_ts = int(rd.timestamp())
        except Exception:
            j.recent_ts = 0
    user = get_user_by_id(user_id)
    # Determine which jobs already have a saved CV PDF on disk
    uploads_dir = Path(app.static_folder) / 'uploads'
    cv_pdf_ids = {
        int(p.stem.replace('cv_', ''))
        for p in uploads_dir.glob('cv_*.pdf')
        if p.stem.replace('cv_', '').isdigit()
    } if uploads_dir.exists() else set()
    # Charger formations et certifications pour les modales avancées
    try:
        _cvd = load_cv_data(app.static_folder)
        cv_education = [
            {
                'idx': i,
                'label': ' - '.join(p for p in [e.get('studyType', ''), e.get('area', '')] if p)
                         or e.get('institution', ''),
                'institution': e.get('institution', ''),
                'year': (e.get('endDate') or '')[:4],
            }
            for i, e in enumerate(_cvd.get('education', []))
        ]
        cv_certificates = [
            {
                'name': c['name'],
                'issuer': c.get('issuer', ''),
                'year': (c.get('date') or '')[:4],
            }
            for c in _cvd.get('certificates', [])
        ]
        cv_skills = [
            {
                'name': s['name'],
                'level': s.get('level', ''),
                'rating': s.get('rating', 0),
            }
            for s in _cvd.get('skills', [])
        ]
        cv_references = [
            {
                'name': r['name'],
                'excerpt': (r.get('reference') or '')[:120].rstrip(),
            }
            for r in _cvd.get('references', [])
        ]
        cv_projects = [
            {
                'name': p['name'],
                'lang': p.get('primaryLanguage', ''),
                'desc': (p.get('summary') or p.get('description') or '')[:80],
            }
            for p in _cvd.get('projects', [])
        ]
    except Exception:
        cv_education = []
        cv_certificates = []
        cv_skills = []
        cv_references = []
        cv_projects = []
    return render_template('candidatures.html', jobs=jobs, user=user, cv_pdf_ids=cv_pdf_ids,
                           cv_education=cv_education, cv_certificates=cv_certificates,
                           cv_skills=cv_skills, cv_references=cv_references, cv_projects=cv_projects)


@app.route('/generate_cover_letter_pdf/<int:id>', endpoint='generate_cover_letter_pdf')
@is_connected
def generate_cover_letter_pdf(id):
    # ...existing code...
    job = Job.query.get_or_404(id)
    try:
        template_path = resolve_cover_letter_template_path(app.static_folder)
        letter_date = datetime.now(app.config['PARIS']) if app.config.get('PARIS') else datetime.now()
        pdf_bytes = generate_cover_letter_pdf_bytes(job=job, template_path=template_path, letter_date=letter_date)
    except FileNotFoundError:
        flash('Le template Word de lettre de motivation est introuvable.', 'error')
        return redirect(url_for('show_all'))
    except RuntimeError as exc:
        app.logger.error(f'Erreur lors de la génération du PDF pour la candidature #{job.id}: {exc}')
        flash(str(exc), 'error')
        return redirect(url_for('show_all'))

    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=build_cover_letter_pdf_filename(job),
    )


@app.route('/preview_cv_data/<int:id>', methods=['POST'])
@is_connected
def preview_cv_data(id):
    """Retourne les suggestions IA de personnalisation du CV au format JSON (pour l'aperçu modal)."""
    job = Job.query.get_or_404(id)
    github_token = app.config.get('GITHUB_TOKEN', '')
    payload = request.get_json(force=True) or {}
    additional_prompt = payload.get('additional_prompt', '')
    ats_mode = bool(payload.get('ats_mode', False))
    if ats_mode:
        additional_prompt = _ft_ats_prefix(True) + additional_prompt
    include_sections = payload.get('include_sections') or []
    # Sélections individuelles formations / certifications
    selected_education = payload.get('selected_education')
    selected_certificates = payload.get('selected_certificates')
    selected_skills = payload.get('selected_skills')
    selected_references = payload.get('selected_references')
    selected_projects = payload.get('selected_projects')

    def _fallback(cv_data, warning=''):
        sugg = {
            'cv_title': cv_data.get('basics', {}).get('label', 'Développeur / Consultant IT'),
            'summary': cv_data.get('basics', {}).get('summary', ''),
            'highlighted_work_indices': list(range(min(4, len(cv_data.get('work', []))))),
            'highlighted_skill_names': [s['name'] for s in cv_data.get('skills', [])[:6]],
            'warning': warning or 'GITHUB_TOKEN non configuré : aperçu généré sans IA.',
            'source': 'fallback',
        }
        wl = cv_data.get('work', [])
        sugg['highlighted_work_details'] = [
            {
                'position': wl[i].get('position', ''),
                'company':  wl[i].get('name', ''),
                'dates':    f"{(wl[i].get('startDate') or '')[:7]} – {(wl[i].get('endDate') or '')[:7] or 'présent'}",
            }
            for i in sugg['highlighted_work_indices'] if 0 <= i < len(wl)
        ]
        return sugg

    try:
        cv_data = load_cv_data(app.static_folder)
        if github_token:
            suggestions = get_ai_cv_suggestions(
                job=job, cv_data=cv_data, github_token=github_token,
                additional_prompt=additional_prompt, include_sections=include_sections,
                selected_education=selected_education, selected_certificates=selected_certificates,
                selected_skills=selected_skills, selected_references=selected_references,
                selected_projects=selected_projects,
            )
        else:
            suggestions = _fallback(cv_data)
            suggestions['_active_sections'] = include_sections
        work_list = cv_data.get('work', [])
        hl_indices = suggestions.get('highlighted_work_indices') or []
        suggestions['highlighted_work_details'] = [
            {
                'position': work_list[i].get('position', ''),
                'company':  work_list[i].get('name', ''),
                'dates':    f"{(work_list[i].get('startDate') or '')[:7]} – {(work_list[i].get('endDate') or '')[:7] or 'présent'}",
            }
            for i in hl_indices if 0 <= i < len(work_list)
        ]
        # Labels lisibles des sections actives pour affichage dans la modale
        _section_labels = {
            'education': '🎓 Formations', 'certificates': '🏅 Certifications',
            'skills_rating': '⭐ Niveaux compétences', 'references': '💬 Références',
            'github_projects': '🐙 Projets GitHub',
        }
        suggestions['active_section_labels'] = [
            _section_labels[s] for s in (suggestions.get('_active_sections') or []) if s in _section_labels
        ]
        return jsonify(suggestions)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:
        app.logger.error(f'preview_cv_data error: {exc}')
        try:
            cv_data = load_cv_data(app.static_folder)
            return jsonify(_fallback(cv_data, warning=f"Aperçu généré sans IA : {exc}")), 200
        except Exception:
            return jsonify({'error': f"Erreur lors de l'appel IA : {exc}"}), 500


@app.route('/save_cv_pdf/<int:id>', methods=['POST'], endpoint='save_cv_pdf')
@is_connected
def save_cv_pdf(id):
    """Génère le CV personnalisé IA, le sauvegarde sur disque et retourne l'URL de téléchargement."""
    job = Job.query.get_or_404(id)
    github_token = app.config.get('GITHUB_TOKEN', '')
    payload = request.get_json(force=True) or {}
    additional_prompt = payload.get('additional_prompt', '')
    ats_mode = bool(payload.get('ats_mode', False))
    if ats_mode:
        additional_prompt = _ft_ats_prefix(True) + additional_prompt
    include_sections = payload.get('include_sections') or []
    selected_education = payload.get('selected_education')
    selected_certificates = payload.get('selected_certificates')
    selected_skills = payload.get('selected_skills')
    selected_references = payload.get('selected_references')
    selected_projects = payload.get('selected_projects')

    def _fallback_suggestions(cv_data, warning=''):
        return {
            'cv_title': cv_data.get('basics', {}).get('label', 'Développeur / Consultant IT'),
            'summary': cv_data.get('basics', {}).get('summary', ''),
            'highlighted_work_indices': list(range(min(4, len(cv_data.get('work', []))))),
            'highlighted_skill_names': [s['name'] for s in cv_data.get('skills', [])[:6]],
            'warning': warning or 'GITHUB_TOKEN non configuré.',
            'source': 'fallback',
        }

    try:
        cv_data = load_cv_data(app.static_folder)
        if github_token:
            suggestions = get_ai_cv_suggestions(
                job=job, cv_data=cv_data, github_token=github_token,
                additional_prompt=additional_prompt, include_sections=include_sections,
                selected_education=selected_education, selected_certificates=selected_certificates,
                selected_skills=selected_skills, selected_references=selected_references,
                selected_projects=selected_projects,
            )
        else:
            suggestions = _fallback_suggestions(cv_data)
        pdf_bytes = generate_tailored_cv_pdf_bytes(
            job=job, cv_data=cv_data, suggestions=suggestions,
            include_sections=include_sections,
            selected_education=selected_education,
            selected_certificates=selected_certificates,
            selected_skills=selected_skills,
            selected_references=selected_references,
            selected_projects=selected_projects,
        )
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:
        app.logger.error(f'save_cv_pdf error: {exc}')
        try:
            cv_data = load_cv_data(app.static_folder)
            suggestions = _fallback_suggestions(cv_data, warning=str(exc))
            pdf_bytes = generate_tailored_cv_pdf_bytes(
                job=job, cv_data=cv_data, suggestions=suggestions,
                include_sections=include_sections,
                selected_education=selected_education,
                selected_certificates=selected_certificates,
                selected_skills=selected_skills,
                selected_references=selected_references,
                selected_projects=selected_projects,
            )
        except Exception as exc2:
            return jsonify({'error': f'Génération PDF échouée : {exc2}'}), 500

    # Sauvegarder sur disque dans static/uploads/
    uploads_dir = Path(app.static_folder) / 'uploads'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    cv_filename = f'cv_{id}.pdf'
    cv_path = uploads_dir / cv_filename
    cv_path.write_bytes(pdf_bytes)

    download_url = url_for('static', filename=f'uploads/{cv_filename}')
    pdf_name = build_cv_pdf_filename(job)
    return jsonify({'url': download_url, 'filename': pdf_name})


@app.route('/generate_cv_pdf/<int:id>', endpoint='generate_cv_pdf')
@is_connected
def generate_cv_pdf(id):
    """Télécharge directement le CV PDF sauvegardé sur disque, ou génère à la volée si absent."""
    job = Job.query.get_or_404(id)
    uploads_dir = Path(app.static_folder) / 'uploads'
    cv_path = uploads_dir / f'cv_{id}.pdf'
    if cv_path.exists():
        return send_file(
            str(cv_path),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=build_cv_pdf_filename(job),
        )
    # Fallback : génération à la volée
    github_token = app.config.get('GITHUB_TOKEN', '')
    try:
        cv_data = load_cv_data(app.static_folder)
        if github_token:
            suggestions = get_ai_cv_suggestions(job=job, cv_data=cv_data, github_token=github_token)
        else:
            suggestions = {
                'cv_title': cv_data.get('basics', {}).get('label', 'Développeur / Consultant IT'),
                'summary': cv_data.get('basics', {}).get('summary', ''),
                'highlighted_work_indices': list(range(min(4, len(cv_data.get('work', []))))),
                'highlighted_skill_names': [s['name'] for s in cv_data.get('skills', [])[:6]],
                'source': 'fallback',
            }
        pdf_bytes = generate_tailored_cv_pdf_bytes(job=job, cv_data=cv_data, suggestions=suggestions)
    except Exception as exc:
        app.logger.error(f'generate_cv_pdf fallback error: {exc}')
        flash(f'Erreur lors de la génération du CV : {exc}', 'error')
        return redirect(url_for('show_all'))

    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=build_cv_pdf_filename(job),
    )


@app.route('/preview_lm_ai/<int:id>', methods=['POST'])
@is_connected
def preview_lm_ai(id):
    """Génère une lettre de motivation par IA et retourne le texte au format JSON."""
    job = Job.query.get_or_404(id)
    github_token = app.config.get('GITHUB_TOKEN', '')
    payload = request.get_json(force=True) or {}
    additional_prompt = payload.get('additional_prompt', '')
    ats_mode = bool(payload.get('ats_mode', False))
    if ats_mode:
        additional_prompt = _ft_ats_prefix(True) + additional_prompt
    include_sections = payload.get('include_sections') or []
    selected_education = payload.get('selected_education')
    selected_certificates = payload.get('selected_certificates')
    selected_skills = payload.get('selected_skills')
    selected_references = payload.get('selected_references')
    selected_projects = payload.get('selected_projects')
    selected_premium_modules = payload.get('selected_premium_modules') or []
    _section_labels = {
        'education': '🎓 Formations', 'certificates': '🏅 Certifications',
        'skills_rating': '⭐ Niveaux compétences', 'references': '💬 Références',
        'github_projects': '🐙 Projets GitHub',
    }
    _premium_labels = {
        'profiles': '🔗 Profils en ligne',
        'languages': '🗣️ Langues',
        'volunteer': '🤝 Bénévolat',
        'awards': '🏆 Distinctions',
        'publications': '📚 Publications',
    }
    try:
        text = get_ai_cover_letter_text(
            job=job, github_token=github_token,
            additional_prompt=additional_prompt, include_sections=include_sections,
            selected_education=selected_education,
            selected_certificates=selected_certificates,
            selected_skills=selected_skills,
            selected_references=selected_references,
            selected_projects=selected_projects,
            selected_premium_modules=selected_premium_modules,
        )
        return jsonify({
            'text': text,
            'active_section_labels': [_section_labels[s] for s in include_sections if s in _section_labels],
            'active_premium_labels': [_premium_labels[s] for s in selected_premium_modules if s in _premium_labels],
        })
    except Exception as exc:
        app.logger.error(f'preview_lm_ai error: {exc}')
        status_code = 429 if ('429' in str(exc) or 'Too Many Requests' in str(exc)) else 500
        return jsonify({'error': str(exc)}), status_code


@app.route('/save_lm_text/<int:id>', methods=['POST'])
@is_connected
def save_lm_text(id):
    """Enregistre le texte de LM généré par IA dans la fiche candidature."""
    job = Job.query.get_or_404(id)
    payload = request.get_json(force=True) or {}
    text = payload.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Texte vide'}), 400
    job.cover_letter_text = text
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/new/', methods=['GET', 'POST'])
@is_connected
@is_editor_or_admin
def new():
    if request.method == 'POST':
        email: str = request.form.get('email', '')
        if not (request.form.get('name') and request.form.get('company')):
            flash('Veuillez remplir tous les champs obligatoires (Offre et Entreprise)', 'error')
            user = get_user_by_id(session['login_id'])
            # return the form with previously entered values
            return render_template('new.html', form_data=request.form, user=user)
        elif email and not check(app.config['REGEX'], email):
            flash(f'E-mail invalide : {email}', 'error')
            user = get_user_by_id(session['login_id'])
            return render_template('new.html', form_data=request.form, user=user)
        else:
            # Create job
            job = Job(name=request.form.get('name'), url=request.form.get('url'),
                      zipCode=request.form.get('zipCode'), company=request.form.get('company'),
                      contact=request.form.get('contact'), date=datetime.now(), email=email,
                      user_id=session['login_id'])
            # Save cover letter text if provided
            cover_text = request.form.get('cover_letter_text')
            if cover_text:
                job.cover_letter_text = cover_text
            db.session.add(job)
            db.session.commit()

            # Handle file upload (capture and cover letter)
            success, error_msg = handle_file_upload(job.id)
            if not success:
                flash(error_msg, 'error')
                user = get_user_by_id(session['login_id'])
                # in case of error, show new form with previous values
                return render_template('new.html', form_data=request.form, user=user)

            # set flags
            if success and 'capture_file' in request.files and request.files['capture_file'].filename:
                job.is_capture = 1
            db.session.commit()

            flash('Record was successfully added')
            return redirect(url_for('show_all'))
    else:
        user = get_user_by_id(session['login_id'])
        return render_template('new.html', form_data=None, user=user)


@app.route('/toggle_expired/<int:id>', methods=['POST'])
@is_connected
@is_editor_or_admin
def toggle_expired(id):
    job = Job.query.get_or_404(id)
    job.active = not job.active
    db.session.commit()
    return '', 200


@app.route('/delete/<int:id>', methods=['GET', 'POST'])
@is_connected
@is_editor_or_admin
def delete(id):
    app.logger.debug(f'Delete job #{id}')
    if request.method == 'GET':
        job = Job.query.get_or_404(id)
        app.logger.debug(f'Job debug: {job}')
        db.session.delete(job)
        db.session.commit()
        flash(f'Job offer \"{job.name}\" from  \"{job.contact}\" was deleted!')
        return redirect(url_for('show_all'))


@app.route('/delete_account/<int:id>', methods=['GET', 'POST'])
@is_connected
@is_admin
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
@is_connected
@is_admin
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
@is_connected
@is_editor_or_admin
def update(id):
    job: Job = Job.query.get_or_404(id)
    def _parse_form_date(value: Optional[str], original: Optional[datetime] = None) -> Optional[datetime]:
        """Parse a date/time coming from the form.
        - Si value est vide, retourne None.
        - Si le formulaire envoie uniquement une date (YYYY-MM-DD, sans heure),
          on préserve l'heure de 'original' pour ne pas écraser le composant horaire
          déjà stocké en base.
        - Accepte aussi les formats datetime-local complets.
        """
        if not value:
            return None
        v = value.strip()
        # Formats avec heure : on les utilise tels quels
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(v, fmt)
            except Exception:
                continue
        # Format date seule (YYYY-MM-DD) : préserver l'heure originale si disponible
        try:
            parsed_date = datetime.strptime(v, "%Y-%m-%d")
            if original is not None:
                return parsed_date.replace(hour=original.hour, minute=original.minute,
                                           second=original.second, microsecond=original.microsecond)
            return parsed_date
        except Exception:
            pass
        # Dernier recours : fromisoformat
        try:
            return datetime.fromisoformat(v)
        except Exception:
            pass
        return None

    if request.method == 'POST':
        job.name = request.form.get('name')
        job.url = request.form.get('url')
        job.zipCode = request.form.get('zipCode')
        job.company = request.form.get('company')
        job.contact = request.form.get('contact')
        job.email = request.form.get('email')

        application_date: str = request.form.get('applicationDate')
        app.logger.debug(f'application_date raw: {application_date}')
        job.applicationDate = _parse_form_date(application_date, original=job.applicationDate)

        relaunch_date: str = request.form.get('relaunchDate')
        job.relaunchDate = _parse_form_date(relaunch_date, original=job.relaunchDate)

        refusal_date: str = request.form.get('refusalDate')
        job.refusalDate = _parse_form_date(refusal_date, original=job.refusalDate)

        # cover letter text
        cover_text = request.form.get('cover_letter_text')
        job.cover_letter_text = cover_text if cover_text else None

        # Handle file upload
        success, error_msg = handle_file_upload(job.id)
        if not success:
            flash(error_msg, 'error')
            return render_template('update.html', job=job)

        if success and 'capture_file' in request.files and request.files['capture_file'].filename:
            job.is_capture = 1

        db.session.commit()
        flash('Record was successfully updated')
        return redirect(url_for('show_all'))
    else:
        return render_template('update.html', job=job)


@app.before_request
def create_tables():
    db.create_all()
    # Migration douce : ajoute les colonnes ajoutées post-création si elles n'existent pas encore
    from sqlalchemy import text as _text
    with db.engine.connect() as _conn:
        _cols = [row[1] for row in _conn.execute(_text("PRAGMA table_info(job)"))]
        if 'ft_offer_id' not in _cols:
            _conn.execute(_text("ALTER TABLE job ADD COLUMN ft_offer_id VARCHAR(30)"))
            _conn.commit()


@app.before_request
def validate_session():
    if 'login_id' in session:
        user_session = Session.query.filter_by(login_id=session['login_id'], end=None).first()
        if not user_session:
            session.clear()
            flash('Votre session a été fermée par un administrateur.', 'warning')
            return redirect(url_for('login'))

@app.before_request
def create_captures_dir():
    directory_path = f'{os.path.dirname(__file__)}/static/images'
    if not os.path.exists(directory_path):
        try:
            os.mkdir(directory_path)
            print(f"Directory {directory_path} created successfully.")
        except Exception as e:
            print(f"Error creating directory: {e}")

@app.route('/lucky')
def upload_form():
    return render_template('upload.html', result=None)

@app.route('/upload', methods=['POST'])
def upload_file():
    result = None
    result_file = None

    if 'file' not in request.files:
        result = 'Aucun fichier n\'a été téléchargé.'
    else:
        file = request.files['file']

        if file.filename == '':
            result = 'Aucun fichier sélectionné.'
        else:
            # Sauvegarder le fichier d'entrée
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            # Traitement du fichier
            sleep(5)
            result_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'result.csv')
            # result_df.to_csv(result_file_path, index=False)

            result = 'Le fichier "{}" a été traité avec succès (Test avec sleep de 5s).'.format(file.filename)
            result_file = result_file_path

    return render_template('upload.html', result=result, result_file=result_file)

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

# ─────────────────────────────────────────────────────────────────────────────
# France Travail – Recherche d'offres
# ─────────────────────────────────────────────────────────────────────────────

def _ft_ats_prefix(ats_mode: bool) -> str:
    """Retourne le préfixe ATS à injecter dans le prompt IA si le mode est activé."""
    if not ats_mode:
        return ''
    return (
        "MODE ATS ACTIVÉ – Optimise ce document pour être correctement traité par les systèmes "
        "ATS (Applicant Tracking System) des recruteurs. Règles strictes : "
        "(1) Utilise EXACTEMENT les mots-clés et formulations de l'offre d'emploi. "
        "(2) Structure le contenu avec des sections et sous-sections claires (pas de colonnes multiples). "
        "(3) Chaque point d'expérience doit commencer par un verbe d'action fort "
        "(Développé, Conçu, Déployé, Optimisé, Géré, Mis en place, Piloté…). "
        "(4) Évite les tableaux complexes, graphiques et icônes dans le contenu textuel. "
        "(5) Le titre doit correspondre mot pour mot à l'intitulé du poste visé.\n\n"
    )


@app.route('/france_travail')
@is_connected
def france_travail():
    user = get_user_by_id(session['login_id'])
    last_extraction = AppSetting.get('ft_last_extraction')
    return render_template(
        'france_travail.html',
        user=user,
        contract_types=CONTRACT_TYPES,
        work_modes=WORK_MODES,
        departments=DEPARTMENTS,
        ats_keywords=ATS_KEYWORDS_PROFILE,
        last_extraction=last_extraction,
        default_dept=app.config.get('FT_DEFAULT_DEPT', '06'),
    )


@app.route('/france_travail/search', methods=['POST'])
@is_connected
def france_travail_search():
    user = get_user_by_id(session['login_id'])
    client_id     = app.config.get('FT_CLIENT_ID', '')
    client_secret = app.config.get('FT_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        flash(
            'Les identifiants France Travail ne sont pas configurés. '
            'Renseignez FT_CLIENT_ID et FT_CLIENT_SECRET dans config.py.',
            'error',
        )
        return redirect(url_for('france_travail'))

    mode       = request.form.get('mode', 'manual')
    departement = request.form.get('departement', '') or None

    try:
        if mode == 'auto':
            cv_data = load_cv_data(app.static_folder)
            min_creation_date = None
            reset_flag = request.form.get('reset_flag') == 'on'
            if not reset_flag:
                last_str = AppSetting.get('ft_last_extraction')
                if last_str:
                    try:
                        min_creation_date = datetime.fromisoformat(last_str)
                    except Exception:
                        pass
            offers = search_auto_from_cv(
                client_id=client_id,
                client_secret=client_secret,
                cv_data=cv_data,
                departement=departement,
                min_creation_date=min_creation_date,
            )
            # Mémoriser la date d'extraction automatique
            AppSetting.set('ft_last_extraction', datetime.utcnow().isoformat())
            depuis = f" depuis le {min_creation_date.strftime('%d/%m/%Y')}" if min_creation_date else ""
            search_info = f"Mode automatique{depuis} – {len(offers)} offre(s) trouvée(s)"
            search_params = {'mode': 'auto', 'departement': departement}
        else:
            mots_cles          = request.form.get('mots_cles', '').strip() or None
            types_contrat      = request.form.getlist('types_contrat') or None
            mode_travail       = request.form.get('mode_travail', '') or None
            entreprises_adapt  = request.form.get('entreprises_adaptees') == 'on'
            offers = search_offers(
                client_id=client_id,
                client_secret=client_secret,
                mots_cles=mots_cles,
                types_contrat=types_contrat,
                departement=departement,
                mode_travail=mode_travail,
                entreprises_adaptees=entreprises_adapt,
            )
            kw   = mots_cles or '(tous)'
            dept = DEPARTMENTS.get(departement or '', departement or 'Toute la France')
            ct   = ', '.join(types_contrat) if types_contrat else 'Tous'
            mt   = mode_travail or 'Tous'
            parts = [f"Mots-clés : \u00ab{kw}\u00bb", f"D\u00e9partement : {dept}",
                     f"Contrats : {ct}", f"Mode : {mt}"]
            if entreprises_adapt:
                parts.append("Handi-engag\u00e9s uniquement")
            search_info = "Mode manuel – " + " | ".join(parts) + f" – {len(offers)} offre(s)"
            search_params = {
                'mode': 'manual', 'mots_cles': mots_cles, 'types_contrat': types_contrat,
                'departement': departement, 'mode_travail': mode_travail,
                'entreprises_adaptees': entreprises_adapt,
            }

    except Exception as exc:
        app.logger.error(f'France Travail search error: {exc}')
        flash(f'Erreur lors de la recherche France Travail : {exc}', 'error')
        return redirect(url_for('france_travail'))

    # Sauvegarde persistante du résultat pour consultation ultérieure
    ft_search = FtSearch(
        user_id=session['login_id'],
        search_info=search_info,
        offers=offers,
        search_params=search_params,
    )
    db.session.add(ft_search)
    db.session.commit()
    return redirect(url_for('ft_search_view', search_id=ft_search.id))


@app.route('/france_travail/searches')
@is_connected
def ft_searches():
    """Liste de toutes les recherches sauvegardées de l'utilisateur."""
    user = get_user_by_id(session['login_id'])
    searches = (
        FtSearch.query
        .filter_by(user_id=session['login_id'])
        .order_by(FtSearch.created_at.desc())
        .all()
    )
    return render_template('ft_searches.html', user=user, searches=searches)


def _ft_added_ids() -> set[str]:
    """Retourne l'ensemble des ft_offer_id déjà présents dans la table job."""
    rows = db.session.query(Job.ft_offer_id).filter(Job.ft_offer_id.isnot(None)).all()
    return {r[0] for r in rows}


@app.route('/france_travail/search/<int:search_id>')
@is_connected
def ft_search_view(search_id):
    """Affiche les résultats d'une recherche sauvegardée."""
    user = get_user_by_id(session['login_id'])
    ft_search = FtSearch.query.get_or_404(search_id)
    return render_template(
        'offers_candidates.html',
        user=user,
        search=ft_search,
        offers=ft_search.offers,
        search_info=ft_search.search_info,
        search_id=search_id,
        added_ids=_ft_added_ids(),
        unavailable_ids=ft_search.unavailable,
    )


@app.route('/france_travail/search/<int:search_id>/refresh', methods=['POST'])
@is_connected
def ft_search_refresh(search_id):
    """Réactualise une recherche sauvegardée en réexécutant les mêmes paramètres."""
    ft_search = FtSearch.query.get_or_404(search_id)
    client_id     = app.config.get('FT_CLIENT_ID', '')
    client_secret = app.config.get('FT_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        flash('Identifiants France Travail non configurés.', 'error')
        return redirect(url_for('ft_search_view', search_id=search_id))

    p = ft_search.params
    try:
        if p.get('mode') == 'auto':
            cv_data = load_cv_data(app.static_folder)
            offers = search_auto_from_cv(
                client_id=client_id, client_secret=client_secret,
                cv_data=cv_data, departement=p.get('departement'),
            )
            search_info = f"Mode automatique (actualisé) – {len(offers)} offre(s)"
        else:
            offers = search_offers(
                client_id=client_id, client_secret=client_secret,
                mots_cles=p.get('mots_cles'), types_contrat=p.get('types_contrat'),
                departement=p.get('departement'), mode_travail=p.get('mode_travail'),
                entreprises_adaptees=bool(p.get('entreprises_adaptees', False)),
            )
            kw = p.get('mots_cles') or '(tous)'
            search_info = f"Mode manuel – Mots-clés : «{kw}» – {len(offers)} offre(s) (actualisé)"
    except Exception as exc:
        app.logger.error(f'FT refresh error: {exc}')
        flash(f'Erreur lors de la réactualisation : {exc}', 'error')
        return redirect(url_for('ft_search_view', search_id=search_id))

    ft_search.offers      = offers
    ft_search.search_info = search_info
    ft_search.created_at  = datetime.utcnow()
    ft_search.unavailable_ids = '[]'
    db.session.commit()
    flash(f'Résultats actualisés – {len(offers)} offre(s) trouvée(s).', 'success')
    return redirect(url_for('ft_search_view', search_id=search_id))


@app.route('/france_travail/search/<int:search_id>/toggle_unavailable', methods=['POST'])
@is_connected
def ft_toggle_unavailable(search_id):
    """Bascule le statut 'indisponible' d'une offre dans une recherche sauvegardée."""
    ft_search = FtSearch.query.get_or_404(search_id)
    offer_id = request.form.get('offer_id', '').strip()
    if offer_id:
        ft_search.toggle_unavailable(offer_id)
        db.session.commit()
    return redirect(url_for('ft_search_view', search_id=search_id))


@app.route('/france_travail/search/<int:search_id>/add_candidature', methods=['POST'])
@is_connected
@is_editor_or_admin
def ft_add_candidature(search_id):
    """Ajoute une offre France Travail comme candidature et reste sur la page de résultats."""
    import re as _re
    offer_id  = request.form.get('offer_id', '').strip()
    title     = request.form.get('title', '').strip()
    url_offer = request.form.get('url', '').strip()
    company   = request.form.get('company', '').strip()
    location  = request.form.get('location', '').strip()

    # Déduplication par identifiant FT (plus fiable que l'URL)
    if offer_id:
        existing = Job.query.filter_by(ft_offer_id=offer_id).first()
        if existing:
            flash(f'La candidature « {title} » ({company}) a déjà été ajoutée !', 'warning')
            return redirect(url_for('ft_search_view', search_id=search_id))

    zip_code = ''
    if location:
        m = _re.search(r'\b(\d{5})\b', location)
        if m:
            zip_code = m.group(1)
        else:
            m2 = _re.search(r'\b(\d{2})\b', location)
            if m2:
                zip_code = m2.group(1)

    job = Job(
        name=title, url=url_offer, zipCode=zip_code, company=company,
        contact='', date=datetime.now(), email='', user_id=session['login_id'],
    )
    job.ft_offer_id = offer_id or None
    db.session.add(job)
    db.session.commit()
    flash(f'Candidature « {title} » ({company}) ajoutée avec succès !', 'success')
    return redirect(url_for('ft_search_view', search_id=search_id))


@app.route('/france_travail/search/<int:search_id>/delete', methods=['POST'])
@is_connected
def ft_search_delete(search_id):
    """Supprime une recherche sauvegardée."""
    ft_search = FtSearch.query.get_or_404(search_id)
    if ft_search.user_id != session['login_id']:
        flash('Action non autorisée.', 'error')
        return redirect(url_for('ft_searches'))
    db.session.delete(ft_search)
    db.session.commit()
    flash('Recherche supprimée.', 'success')
    return redirect(url_for('ft_searches'))


# ─────────────────────────────────────────────────────────────────────────────


@app.template_filter('format_paris_time')
def format_paris_time(utc_dt):
    paris_tz = timezone('Europe/Paris')
    paris_time = utc_dt.astimezone(paris_tz)
    return paris_time.strftime('%A %d %B %Y à %Hh%M')


# if app.config['SCHEDULER']:
#     app.logger.debug(app.config['SCHEDULER'])
#     scheduler = BackgroundScheduler()
#     scheduler.add_job(func=send_reminders, trigger="interval", seconds=app.config['SCHEDULER_INTERVAL'])
#     scheduler.start()
#
#     # Shut down the scheduler when exiting the app
#     atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app.run()
    toolbar.init_app(app)
    app.run(debug=True, use_debugger=True, use_reloader=False)
