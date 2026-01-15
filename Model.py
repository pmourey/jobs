from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Match

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
