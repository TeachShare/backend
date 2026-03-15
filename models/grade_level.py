from . import db

class GradeLevel(db.Model):
    __tablename__ = 'grade_level'
    grade_level_id = db.Column(db.Integer, primary_key=True)
    grade_name = db.Column(db.String(30), nullable=False)
    tier = db.Column(db.String(20), nullable=False)
    rank = db.Column(db.Integer, nullable=False)

