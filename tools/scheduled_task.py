from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime

from config import Config
from flask_app import paris
from tools.send_emails import send_email


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/jobs.sqlite3'
db = SQLAlchemy(app)
config = Config()

class Job(db.Model):
    __tablename__ = 'jobs'
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


def send_fake_email(job: Job, author: str, cv_resume: str) -> bool:
    first_name: str = job.contact.split()[0]
    body = f'''Bonjour {first_name},<br>
<br>
J'ai postulé le <mark>{job.applicationDate.strftime('%d %B %Y')}</mark> à l'offre \"{job.name}\" au sein de votre société.<br>
<br>
Je me permets de vous demander si ce poste est toujours vacant et si dans le cas contraire, vous auriez actuellement des missions en adéquation avec mon profil.<br>
<br>
En vous remerciant pour votre retour.<br>
<br>
Cordialement,<br>
{author}.<br>
{cv_resume}.<br>
(mail généré par automate <a href=https://pypi.org/project/Flask-APScheduler/>Flask-APScheduler</a>)'''

    # if send_email_old(to=job.email, subject=f'Relance candidature {job.name}', body=body):
    if send_email(subject=f'Relance candidature {job.name}',
                  body=body,
                  sender_email=config['GMAIL_USER'],
                  recipient_email=job.email,
                  bcc_recipients=[config['GMAIL_USER']],
                  smtp_server=config['SMTP_SERVER'],
                  smtp_port=config['SMTP_PORT'],
                  username=config['GMAIL_USER'],
                  password=config['GMAIL_APP_PWD'],
                  author=config['GMAIL_FULLNAME'],
                  ):
        job.relaunchDate = datetime.now(paris)
        return True
    return False

with app.app_context():
    jobs = Job.query.all()
    for job in jobs:
        print(job.contact)
        first_name: str = job.contact.split()[0] if job.contact else ''
        if first_name in ['Fifi', 'Frérot'] and job.active and not job.refusalDate and job.email:
            print(first_name)
            # Calculate the difference between the two dates
            if job.relaunchDate:
                difference = relativedelta(datetime.now(), job.relaunchDate)
            else:
                difference = relativedelta(datetime.now(), job.applicationDate)
            # print(f'months = {difference.months} - days = {difference.days}')
            if difference.months >= 1:  # and difference.years == 0 and difference.days == 0:
                if send_fake_email(job=job, author=config['GMAIL_FULLNAME'], cv_resume=config['CV_RESUME']):
                    print(f'Message sent to {job.email}.')

