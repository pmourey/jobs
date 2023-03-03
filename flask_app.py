import requests
from logging import basicConfig, DEBUG

import locale
import os
from datetime import datetime
from pytz import timezone

from flask import Flask, request, flash, url_for, redirect, render_template

from flask_sqlalchemy import SQLAlchemy
from requests.exceptions import MissingSchema
from sqlalchemy import DateTime
from validators import url

# SQLite
# sqlite3_db = '/Users/display/Library/DBeaverData/workspace6/.metadata/sample-database-sqlite-1/Chinook.db'
# uri: str = f'sqlite:///{sqlite3_db}'
# MySQL
# hostname: str = 'pmourey.mysql.pythonanywhere-services.com'
# uri = f'mysql://pmourey:fifa2022@{hostname}/sample'
# mysql://username:password@server/db

app = Flask(__name__, static_folder='captures')
# app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.sqlite3'
app.config['SECRET_KEY'] = "fifa 2022"

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
    date = db.Column(db.DateTime)
    active = db.Column(db.Integer)

    def __init__(self, name: str, url: str, zipCode: str, company: str, contact: str, date: DateTime):
        self.name = name
        self.url = url
        self.zipCode = zipCode
        self.company = company
        self.contact = contact
        self.date = date
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
    def capture(self) -> str:
        path = os.path.dirname(__file__)
        file_name: str = f'capture_id#{self.id}.png'
        if not os.path.isfile(f'{path}/captures/{file_name}'):
            return None
        return file_name


@app.route('/')
def show_all():
    return render_template('show_all.html', jobs=Job.query.all())


@app.route('/new', methods=['GET', 'POST'])
def new():
    paris = timezone('Europe/Paris')
    if request.method == 'POST':
        if not request.form['name'] or not request.form['url'] or not request.form['company']:
            flash('Please enter all the fields', 'error')
        else:
            job = Job(name=request.form['name'], url=request.form['url'],
                      zipCode=request.form['zipCode'], company=request.form['company'], contact=request.form['contact'], date=datetime.now(paris))

            db.session.add(job)
            db.session.commit()
            flash('Record was successfully added')
            return redirect(url_for('show_all'))
    return render_template('new.html')


@app.before_request
def create_tables():
    db.create_all()


if __name__ == '__main__':
    # db.create_all()
    app.run(debug=True)
