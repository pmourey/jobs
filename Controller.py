from __future__ import annotations

import re
from datetime import datetime
from typing import Match

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from Model import Job, User, db, Session
from tools.send_emails import send_email


def get_user_by_username_and_password(username, password) -> User:
    # Hash le mot de passe avant de le comparer dans la requête
    # hashed_password = # Utilisez une fonction de hachage (par exemple, hash_password(password))

    # Effectue la requête pour récupérer un utilisateur par nom d'utilisateur et mot de passe
    return User.query.filter_by(username=username, password=password).first()


def get_user_by_id(user_id: int) -> User:
    # Effectue la requête pour récupérer un utilisateur par nom d'utilisateur et mot de passe
    return User.query.filter_by(id=user_id).first()

def get_session_by_login(username: str) -> Session:
    # Récupère la session la plus récente
    return Session.query.filter_by(login=username).order_by(Session.start.desc()).first()

def check(regex: str, email: str) -> Match[str] | None:
    return re.fullmatch(regex, email)


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
