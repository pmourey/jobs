# config.py
from pytz import timezone
from ollama_tuning import IMAC_64GB_OLLAMA_TUNING


class Config:
    DEBUG = False
    # TESTING = True
    SECRET_KEY = 'fifa 2022'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///jobs.sqlite3'
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 465
    GMAIL_FULLNAME = 'Philippe Mourey'
    GMAIL_USER = 'philippe.mourey@gmail.com'
    GMAIL_APP_PWD = "your GMail Application password"
    CV_RESUME = 'https://www.linkedin.com/in/pmourey/<br>https://github.com/pmourey/jobs<br>https://pmourey.github.io/portfolio/'
    GITHUB_TOKEN = 'ollama-local'
    GITHUB_MODELS_BASE_URL = 'http://localhost:11434'
    GITHUB_MODELS_MODEL = 'llama3.1:8b'
    OLLAMA_LOCAL_TUNING = IMAC_64GB_OLLAMA_TUNING
    # Enable or disable outbound AI model calls (GitHub Models / OpenAI-compatible).
    # On hosts that block outgoing connections (ex: PythonAnywhere), set this to False
    # to force local fallbacks for CV / LM generation.
    ENABLE_REMOTE_IA = True
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
