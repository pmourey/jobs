class Job(db.Model):
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
                app.logger.debug(self.applicationDate)
                app.logger.debug(f'{difference.days} days - {difference.months} months')
                return difference.days >= 10
        return False