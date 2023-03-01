import locale
from datetime import datetime#, timezone
from pytz import timezone

from enum import Enum

from flask import Flask, request, flash, url_for, redirect, render_template

# https://pypi.org/project/flask/FLAS-sqlalchemy/
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime

# SQLite
# sqlite3_db = '/Users/display/Library/DBeaverData/workspace6/.metadata/sample-database-sqlite-1/Chinook.db'
# uri: str = f'sqlite:///{sqlite3_db}'
# MySQL
# hostname: str = 'pmourey.mysql.pythonanywhere-services.com'
# uri = f'mysql://pmourey:fifa2022@{hostname}/sample'
# mysql://username:password@server/db

app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.sqlite3'
app.config['SECRET_KEY'] = "fifa 2022"

db = SQLAlchemy(app)
locale.setlocale(locale.LC_TIME, 'fr_FR')


class Job(db.Model):
    id = db.Column('job_id', db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    url = db.Column(db.String(100))
    zipCode = db.Column(db.String(5))
    company = db.Column(db.String(20))
    contact = db.Column(db.String(20))
    date = db.Column(db.DateTime)

    def __init__(self, name: str, url: str, zipCode: str, company: str, contact: str, date: DateTime):
        self.name = name
        self.url = url
        self.zipCode = zipCode
        self.company = company
        self.contact = contact
        self.date = date


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
            job = Job(request.form['name'], request.form['url'],
                      request.form['zipCode'], request.form['company'], request.form['contact'], datetime.now(paris))

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
