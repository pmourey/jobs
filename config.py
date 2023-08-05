# config.py

class Config:
    DEBUG = False
    # TESTING = True
    SECRET_KEY = 'fifa 2022'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///jobs.sqlite3'
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 465
    GMAIL_FULLNAME = 'Philippe Mourey'
    GMAIL_USER = 'philippe@mourey.com'
    GMAIL_APP_PWD = 'xxxxxxxxxxx'
    CV_RESUME = 'https://www.linkedin.com/in/pmourey/'
    SCHEDULER = False
    SCHEDULER_INTERVAL = 3600 * 24
    # SCHEDULER_INTERVAL = 10
    # Add other configuration variables here
    ALL_CONTACTS = True # useless if scheduler is off


class DevelopmentConfig(Config):
    DEBUG = True
    DEBUG_TB_INTERCEPT_REDIRECTS = True
    ENV = 'development'


class ProductionConfig(Config):
    # Add production-specific configuration here
    pass
