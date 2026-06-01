from __future__ import annotations

import json as _json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Match, Optional

from dateutil.relativedelta import relativedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import relationship, validates
from validators import url
from werkzeug.security import generate_password_hash

db = SQLAlchemy()


class Role(Enum):
    ADMIN = 0
    EDITOR = 1
    READER = 2


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.Integer)
    creationDate = db.Column(db.DateTime, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    recovery_token = db.Column(db.String(128))
    token_expiration = db.Column(db.DateTime)
    validated = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'{self.username}:{self.password} ({Role(self.role)})'

    def __init__(self, username: str, password: str, creation_date: DateTime, email: str):
        self.username = username
        self.password = generate_password_hash(password)
        # self.password = generate_password_hash(password, method='scrypt')
        self.creationDate = creation_date
        self.email = email
        self.role = Role.READER.value

    # @validates('email')
    # def validate_email(self, email):
    #     return email.lower() if email else None

    @validates('email')
    def validates(self, key, email):
        if email is None:
            return None

        # Remove leading/trailing whitespace
        email = email.strip()

        # Email pattern regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(pattern, email):
            raise ValueError('Invalid email format')

        return email.lower()

    @property
    def is_admin(self):
        return Role(self.role) == Role.ADMIN

    @property
    def is_editor(self):
        return Role(self.role) == Role.EDITOR

    @property
    def is_reader(self):
        return Role(self.role) == Role.READER


@dataclass
class BrowserInfo:
    family: str
    version: str


class Session(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=True)
    client_ip = db.Column(db.String(15), nullable=False)
    browser_family = db.Column(db.String(20), nullable=False)
    browser_version = db.Column(db.String(10), nullable=False)
    login_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        user: User = User.query.get(self.login_id)
        if not self.end:
            return f'{user.username} connecté depuis: {self.start}'
        else:
            return f'{user.username} déconnecté à: {self.end}'

    @property
    def user(self):
        return User.query.get(self.login_id)

    @property
    def username(self) -> str:
        return User.query.get(self.login_id).username

    def __init__(self, login_id: int, start: DateTime, client_ip: str, browser_family: str, browser_version: str):
        self.login_id = login_id
        self.start = start
        self.end = None
        self.client_ip = client_ip
        self.browser_family = browser_family
        self.browser_version = browser_version


class Job(db.Model):
    __tablename__ = 'job'
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cover_letter_text = db.Column(db.Text)
    ft_offer_id = db.Column(db.String(30), nullable=True, index=True)

    # Relation avec la table Utilisateur
    # utilisateur = relationship('user', backref='job')
    # utilisateur = relationship('User')

    def __repr__(self):
        return f'{self.name}'

    def __init__(self, name: str, url: str, zipCode: str, company: str, contact: str, date: DateTime, email: str,
                 user_id: int):
        self.name = name
        self.url = url
        self.zipCode = zipCode
        self.company = company
        self.contact = contact
        self.applicationDate = date
        self.email = email
        self.relaunchDate = None
        self.refusalDate = None
        self.user_id = user_id
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
        if not self.refusalDate:  # and self.email:
            # app.logger.debug(self.first_name)
            # Calculate the difference between the two dates
            if self.relaunchDate:
                difference = relativedelta(datetime.now(), self.relaunchDate)
                return difference.months >= 1
            else:
                difference = relativedelta(datetime.now(), self.applicationDate)
                # logging.info(self.applicationDate)
                # logging.info(f'{difference.days} days - {difference.months} months')
                return difference.days >= 10
        return False

    def capture_exists(self) -> bool:
        path = os.path.dirname(__file__)
        file_name: str = f'capture_{self.id}.pdf'
        return os.path.isfile(f'{path}/static/images/{file_name}')


class AppSetting(db.Model):
    """Table de configuration applicative clé/valeur.

    Utilisée notamment pour mémoriser la date de la dernière extraction
    automatique France Travail (clé : 'ft_last_extraction').
    """
    __tablename__ = 'app_setting'
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500))

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        """Retourne la valeur associée à la clé, ou default si absente."""
        s = AppSetting.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key: str, value: str) -> None:
        """Crée ou met à jour la clé et commite la session."""
        s = AppSetting.query.filter_by(key=key).first()
        if s:
            s.value = value
        else:
            s = AppSetting(key=key, value=value)
            db.session.add(s)
        db.session.commit()


class FtSearch(db.Model):
    """Sauvegarde persistante des résultats de recherche France Travail.

    Permet de consulter les résultats ultérieurement et de les réactualiser.
    """
    __tablename__ = 'ft_search'
    id                  = db.Column(db.Integer, primary_key=True)
    created_at          = db.Column(db.DateTime, nullable=False)
    search_info         = db.Column(db.String(300))
    offers_json         = db.Column(db.Text)          # liste JSON des offres normalisées
    unavailable_ids     = db.Column(db.Text, default='[]')  # IDs FT marqués "indisponible"
    search_params_json  = db.Column(db.Text)          # paramètres pour la réactualisation
    user_id             = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, user_id: int, search_info: str, offers: list, search_params: dict):
        self.user_id            = user_id
        self.created_at         = datetime.utcnow()
        self.search_info        = search_info
        self.offers_json        = _json.dumps(offers, ensure_ascii=False)
        self.unavailable_ids    = '[]'
        self.search_params_json = _json.dumps(search_params, ensure_ascii=False)

    @property
    def offers(self) -> list:
        return _json.loads(self.offers_json or '[]')

    @offers.setter
    def offers(self, value: list) -> None:
        self.offers_json = _json.dumps(value, ensure_ascii=False)

    @property
    def params(self) -> dict:
        return _json.loads(self.search_params_json or '{}')

    @property
    def unavailable(self) -> set:
        return set(_json.loads(self.unavailable_ids or '[]'))

    def toggle_unavailable(self, ft_id: str) -> None:
        """Bascule l'état indisponible d'une offre (ajoute si absent, retire si présent)."""
        ids = _json.loads(self.unavailable_ids or '[]')
        if ft_id in ids:
            ids.remove(ft_id)
        else:
            ids.append(ft_id)
        self.unavailable_ids = _json.dumps(ids)
