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
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import timezone
from flask import Flask, request, flash, url_for, redirect, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy import DateTime, desc
from validators import url
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from tools.send_emails import send_email

app = Flask(__name__, static_folder='static', static_url_path='/static')
# Set the environment (development, production, etc.)
# Replace 'development' with the appropriate value for your environment
app.config.from_object('config.Config')

toolbar = DebugToolbarExtension(app)
paris = timezone('Europe/Paris')
regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

db = SQLAlchemy(app)
locale.setlocale(locale.LC_TIME, 'fr_FR')
basicConfig(level=DEBUG)


class Job(db.Model):
    id = db.Column('job_id', db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    url = db.Column(db.String(100))
    zipCode = db.Column(db.String(5))
    company = db.Column(db.String(20))
    contact = db.Column(db.String(20))
    email = db.Column(db.String(40))
    applicationDate = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Integer)
    is_capture = db.Column(db.Integer)
    relaunchDate = db.Column(db.DateTime)
    refusalDate = db.Column(db.DateTime)

    def __repr__(self):
        return f'{self.name}'

    def __init__(self, name: str, url: str, zipCode: str, company: str, contact: str, date: DateTime, email: str):
        self.name = name
        self.url = url
        self.zipCode = zipCode
        self.company = company
        self.contact = contact
        self.applicationDate = date
        self.email = email
        self.relaunchDate = None
        self.refusalDate = None
        self.active = True

    @property
    def valid_url(self) -> bool:
        try:
            result = url(self.url)
            # request_response = requests.head(self.url)
        except Exception:
            return False
        return result

    @property
    def first_name(self) -> Optional[str]:
        return self.contact.split()[0] if self.contact else ''

    @property
    def expired(self) -> bool:
        if not self.refusalDate and self.email:
            # app.logger.debug(self.first_name)
            # Calculate the difference between the two dates
            if self.relaunchDate:
                difference = relativedelta(datetime.now(), self.relaunchDate)
                return difference.months >= 1
            else:
                difference = relativedelta(datetime.now(), self.applicationDate)
                app.logger.debug(self.applicationDate)
                app.logger.debug(f'{difference.days} days - {difference.months} months')
                return difference.days >= 10
        return False

    def capture_exists(self) -> bool:
        path = os.path.dirname(__file__)
        file_name: str = f'capture_{self.id}.pdf'
        return os.path.isfile(f'{path}/static/images/{file_name}')


def check(email: str) -> Match[str] | None:
    return re.fullmatch(regex, email)


def send_fake_email(job: Job, author: str, cv_resume: str) -> bool:
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
        job.relaunchDate = datetime.now(paris)
        db.session.commit()
        return True
    return False


def send_reminders():
    with app.app_context():
        # date: str = datetime.now().strftime("%A, %d. %B %Y %I:%M:%S %p")
        jobs = Job.query.filter(Job.active).all() if app.config['ALL_CONTACTS'] else Job.query.filter((Job.active) & (Job.contact == 'Fifi')).all()
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


# if __name__ == '__main__':

@app.route('/')
def show_all():
    app.logger.debug('This is a debug message.')
    # Reverse order query
    jobs = Job.query.filter(Job.active).order_by(desc(Job.applicationDate)).all()
    return render_template('index.html', jobs=jobs)


@app.route('/new/', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        email: str = request.form['email']
        if not (request.form['name'] and request.form['url'] and request.form['company']):
            flash('Please enter all the fields', 'error')
        elif email and not check(email):
            flash(f'Invalid E-Mail {email}!', 'error')
        else:
            job = Job(name=request.form['name'], url=request.form['url'],
                      zipCode=request.form['zipCode'], company=request.form['company'],
                      contact=request.form['contact'], date=datetime.now(paris), email=email)
            # logging.warning("See this message in Flask Debug Toolbar!")
            job.is_capture = job.capture_exists()
            db.session.add(job)
            db.session.commit()
            flash('Record was successfully added')
    return redirect(url_for('show_all'))
    # return render_template('index.html')


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
