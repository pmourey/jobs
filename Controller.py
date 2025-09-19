from __future__ import annotations

import os
import re
from datetime import datetime
from functools import wraps
from typing import Match

from dateutil.relativedelta import relativedelta
from flask import request
from werkzeug.security import generate_password_hash

from Model import Job, User, db, Session
from tools.send_emails import send_email

""" Hash functions """
from werkzeug.security import generate_password_hash, check_password_hash as werkzeug_check_password_hash
import hashlib

# Define legacy hash methods here
LEGACY_HASH_METHODS = {'sha256': lambda stored, pwd: stored == hashlib.sha256(pwd.encode()).hexdigest(), 'md5': lambda stored, pwd: stored == hashlib.md5(pwd.encode()).hexdigest(), # Add more if needed in the future
}


def check_password_and_upgrade(user, password):
    """
    Check password against multiple hash schemes, upgrade to Werkzeug hash automatically.

    Args:
        user: User object with .password attribute
        password: Plaintext password to check
        db: SQLAlchemy session for committing upgrades
    Returns:
        True if password is correct, False otherwise
    """
    password_hash = user.password

    try:
        # First, try Werkzeug's check
        if werkzeug_check_password_hash(password_hash, password):
            return True
        return False
    except ValueError as e:
        # Werkzeug does not recognize the hash method
        for method_name, checker in LEGACY_HASH_METHODS.items():
            if checker(password_hash, password):
                # Upgrade password to secure Werkzeug hash
                user.password = generate_password_hash(password)
                db.session.commit()
                return True
        return False


""" SQL Alchemy requests """

def get_user_by_id(user_id: int) -> User:
    # Effectue la requête pour récupérer un utilisateur par nom d'utilisateur et mot de passe
    return User.query.filter_by(id=user_id).first()


def get_session_by_login(username: str) -> Session:
    # Récupère la session la plus récente
    user: User = User.query.filter_by(username=username).first()
    return Session.query.filter_by(login_id=user.id).order_by(Session.start.desc()).first()


""" Utilities """


def check(regex: str, email: str) -> Match[str] | None:
    return re.fullmatch(regex, email)


def handle_file_upload(job_id):
    """Handle PDF file upload with validation. Returns (success, error_message)"""
    if 'capture_file' not in request.files:
        return True, None
    
    file = request.files['capture_file']
    if not file or not file.filename:
        return True, None
    
    # Check file size (2MB max)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > 2 * 1024 * 1024:
        return False, 'Erreur: Le fichier ne doit pas dépasser 2Mo!'
    
    # Check PDF header
    header = file.read(4)
    file.seek(0)
    if header != b'%PDF':
        return False, 'Erreur: Le fichier n\'est pas un PDF valide!'
    
    # Save file
    filename = f'capture_{job_id}.pdf'
    images_dir = os.path.join(os.path.dirname(__file__), 'static', 'images')
    os.makedirs(images_dir, exist_ok=True)
    file_path = os.path.join(images_dir, filename)
    file.save(file_path)
    return True, None


""" Back-end features """

def send_confirmation_email(app, confirm_link: str, user: User, author: str, cv_resume: str) -> bool:
    subject: str = f'Confirmation de l\'inscription (Suivi des candidatures)'
    body = f'''Bonjour {user.username},<br>
    <br>Une demande de création de compte a été effectuée sur l'application Flask <a href=http://pmourey.pythonanywhere.com">"Suivi de candidatures"</a></br>
    <br>
    <br>Veuillez clicker <a href={confirm_link}>ICI</a> pour confirmer votre inscription, svp.<br>
    <br>
    <br>Si vous avez aimé l'application, n'hésitez pas à me le faire savoir ou à la partager à vos amis ou collègues.<br>
    <br>En vous souhaitant une bonne journée.<br>
    <br>
    Cordialement,<br>
    {author}.<br><br>
    {cv_resume}.<br>'''
    return send_email(subject=subject,
                  body=body,
                  sender_email=app.config['GMAIL_USER'],
                  recipient_email=f'"{user.username}"<{user.email}>',
                  bcc_recipients=[app.config['GMAIL_USER']],
                  smtp_server=app.config['SMTP_SERVER'],
                  smtp_port=app.config['SMTP_PORT'],
                  username=app.config['GMAIL_USER'],
                  password=app.config['GMAIL_APP_PWD'],
                  author=app.config['GMAIL_FULLNAME'],
                  )

def send_password_recovery_email(app, reset_link: str, user: User, author: str, cv_resume: str) -> bool:
    subject: str = f'Demande de réinitialisation de mot de passe (Suivi des candidatures)'
    body = f'''Bonjour {user.username},<br>
    <br>Vous êtes utilisateur de l'application Flask "Suivi de candidatures", et une demande de réinitialisation de mot de passe a été effectuée</br>
    <br>Veuillez clicker sur le lien ci-dessous pour lancer le formulaire de réinitialisation.<br>
    <br>{reset_link}<br>
    <br>Si vous avez aimé l'application, n'hésitez pas à me le faire savoir ou à la partager à vos amis ou collègues.<br>
    <br>En vous souhaitant une bonne journée.<br>
    <br>
    Cordialement,<br>
    {author}.<br>
    {cv_resume}.<br>'''
    return send_email(subject=subject,
                  body=body,
                  sender_email=app.config['GMAIL_USER'],
                  recipient_email=f'"{user.username}"<{user.email}>',
                  bcc_recipients=[app.config['GMAIL_USER']],
                  smtp_server=app.config['SMTP_SERVER'],
                  smtp_port=app.config['SMTP_PORT'],
                  username=app.config['GMAIL_USER'],
                  password=app.config['GMAIL_APP_PWD'],
                  author=app.config['GMAIL_FULLNAME'],
                  )


def send_fake_email(app, job: Job, author: str, cv_resume: str) -> bool:
    if job.name == 'Prise de contact':
        subject: str = f'Relance suite prise de contact'
        content: str = f'''Nous avons échangé le {job.applicationDate.strftime('%d %B %Y')} concernant des offres d'emploi auprès de votre société pouvant correspondre à mon profil.<br>
<br>
Je me permets de vous relancer mensuellement pour connaître le statut d'avancement de ma candidature auprès de votre société.<br>
'''
    else:
        subject: str = f'Relance candidature {job.name}'
        content: str = f'''J'ai postulé le <mark>{job.applicationDate.strftime('%d %B %Y')}</mark> à l'offre \"{job.name}\" au sein de votre société.<br><br>
Je me permets de vous demander si ce poste est toujours vacant et si dans le cas contraire, vous auriez actuellement des missions en adéquation avec mon profil.<br>
'''

    body = f'''Bonjour {job.first_name},<br>
<br>{content}<br>
En vous remerciant pour votre retour.<br>
<br>
Cordialement,<br>
{author}.<br>
{cv_resume}.<br>
(mail généré par automate <a href=https://pypi.org/project/Flask-APScheduler/>Flask-APScheduler</a>)'''

    # if send_email_old(to=job.email, subject=f'Relance candidature {job.name}', body=body):
    if send_email(subject=subject,
                  body=body,
                  sender_email=app.config['GMAIL_USER'],
                  recipient_email=f'"{job.first_name}"<{job.email}>',
                  bcc_recipients=[app.config['GMAIL_USER']],
                  smtp_server=app.config['SMTP_SERVER'],
                  smtp_port=app.config['SMTP_PORT'],
                  username=app.config['GMAIL_USER'],
                  password=app.config['GMAIL_APP_PWD'],
                  author=app.config['GMAIL_FULLNAME'],
                  ):
        job.relaunchDate = datetime.now(app.config.paris)
        db.session.commit()
        return True
    return False


def send_reminders(app):
    with app.app_context():
        # date: str = datetime.now().strftime("%A, %d. %B %Y %I:%M:%S %p")
        jobs = Job.query.filter(Job.active).all() if app.config['ALL_CONTACTS'] else Job.query.filter(
            (Job.active) & (Job.contact == 'Fifi')).all()
        for job in jobs:
            if not job.refusalDate and job.email:
                app.logger.debug(job.first_name)
                # Calculate the difference between the two dates
                if job.relaunchDate:
                    difference = relativedelta(datetime.now(), job.relaunchDate)
                else:
                    difference = relativedelta(datetime.now(), job.applicationDate)
                # app.logger.debug(f'months = {difference.months} - days = {difference.days}')
                if difference.months >= 1:  # and difference.years == 0 and difference.days == 0:
                    if send_fake_email(job=job, author=app.config['GMAIL_FULLNAME'], cv_resume=app.config['CV_RESUME']):
                        app.logger.debug(f'Message sent to {job.email}.')
