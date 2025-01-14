# config.py
from pytz import timezone


class Config:
    DEBUG = True
    # TESTING = True
    SECRET_KEY = 'fifa 2022'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///jobs.sqlite3'
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 465
    GMAIL_FULLNAME = 'Philippe Mourey'
    GMAIL_USER = 'philippe@mourey.com'
    GMAIL_APP_PWD = 'vjkpggrtalpqohry'
    CV_RESUME = 'https://www.linkedin.com/in/pmourey/<br>https://github.com/pmourey/jobs<br>https://pmourey.github.io/portfolio/'
    SCHEDULER = False
    SCHEDULER_INTERVAL = 3600 * 24
    # SCHEDULER_INTERVAL = 10
    # Add other configuration variables here
    ALL_CONTACTS = True # useless if scheduler is off
    PARIS = timezone('Europe/Paris')
    REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'


class DevelopmentConfig(Config):
    DEBUG = True
    DEBUG_TB_INTERCEPT_REDIRECTS = True
    ENV = 'development'


class ProductionConfig(Config):
    # Add production-specific configuration here
    pass
