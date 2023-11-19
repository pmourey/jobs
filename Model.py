from __future__ import annotations

import os
import re
from datetime import datetime
from enum import Enum
from typing import Optional, Match

from dateutil.relativedelta import relativedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import relationship
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

    def __repr__(self):
        return f'{self.username}:{self.password} ({Role(self.role)})'

    def __init__(self, username: str, password: str, creation_date: DateTime, email: str):
        self.username = username
        self.password = generate_password_hash(password, method='sha256')
        self.creationDate = creation_date
        self.email = email
        self.role = Role.READER.value

    @property
    def is_admin(self):
        return Role(self.role) == Role.ADMIN

    @property
    def is_editor(self):
        return Role(self.role) == Role.EDITOR

    @property
    def is_reader(self):
        return Role(self.role) == Role.READER

class Session(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    login = db.Column(db.String(20), unique=False, nullable=False)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        if not self.end:
            return f'{self.login} connecté depuis: {self.start}'
        else:
            return f'{self.login} déconnecté à: {self.end}'

    def __init__(self, login: str, start: DateTime):
        self.login = login
        self.start = start
        self.end = None


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
        if not self.refusalDate and self.email:
            # app.logger.debug(self.first_name)
            # Calculate the difference between the two dates
            if self.relaunchDate:
                difference = relativedelta(datetime.now(), self.relaunchDate)
                return difference.months >= 1
            else:
                difference = relativedelta(datetime.now(), self.applicationDate)
                # app.logger.debug(self.applicationDate)
                # app.logger.debug(f'{difference.days} days - {difference.months} months')
                return difference.days >= 10
        return False

    def capture_exists(self) -> bool:
        path = os.path.dirname(__file__)
        file_name: str = f'capture_{self.id}.pdf'
        return os.path.isfile(f'{path}/static/images/{file_name}')
