from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime, Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class JobOld(Base):
    __tablename__ = 'jobs'
    job_id = Column(Integer, primary_key=True)
    name = Column(String(100))
    url = Column(String(100))
    zipCode = Column(String(5))
    company = Column(String(20))
    contact = Column(String(20))
    email = Column(String(40))
    applicationDate = Column(DateTime, nullable=False)
    active = Column(Integer)
    is_capture = Column(Integer)
    relaunchDate = Column(DateTime)
    refusalDate = Column(DateTime)

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
