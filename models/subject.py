from . import db

class Subject(db.Model):
    __tablename__ = 'subject'
    subject_id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(240), nullable=False, unique=True)
    tier = db.Column(db.String(20), nullable=True)
    rank = db.Column(db.Integer, nullable=True)