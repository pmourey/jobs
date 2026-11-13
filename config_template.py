# config.py
from pytz import timezone
from ollama_tuning import IMAC_64GB_OLLAMA_TUNING


class Config:
    DEBUG = False
    # Mode communautaire gratuit : aucun paiement ni avantage payant n'est
    # activé par l'application. Un lien de soutien doit rester vide tant que
    # son cadre fiscal et les conditions du prestataire ne sont pas vérifiés.
    COMMUNITY_MODE = True
    COMMUNITY_SUPPORT_URL = ''
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
    # Fournisseurs d'offres autorisés par défaut ; l'Admin peut les activer
    # ou désactiver depuis le menu dédié.
    JOB_OFFER_ENABLED_PROVIDERS = 'france_travail'
    FT_CLIENT_ID = ''
    FT_CLIENT_SECRET = ''
    ADZUNA_APP_ID = ''
    ADZUNA_APP_KEY = ''
    ADZUNA_COUNTRY = 'fr'
    JOOBLE_API_KEY = ''
    JOOBLE_BASE_URL = 'https://jooble.org/api'
    # Enable or disable outbound AI model calls (GitHub Models / OpenAI-compatible).
    # On hosts that block outgoing connections (ex: PythonAnywhere), set this to False
    # to force local fallbacks for CV / LM generation.
    ENABLE_REMOTE_IA = True
    # Fernet key generated with:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Never commit the value; set AI_CREDENTIALS_MASTER_KEY in the environment.
    AI_CREDENTIALS_MASTER_KEY = ''
    AI_ENABLED_PROVIDERS = 'gemini,openai,mistral,openrouter,groq'
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
