from . import db
from datetime import datetime

class Teacher(db.Model):
    __tablename__ = 'teachers'
    teacher_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)

    profile_image_url = db.Column(db.String(255), nullable=True)
    joined_date = db.Column(db.DateTime, default=datetime.utcnow) 
    
    auth = db.relationship('UserAuth', backref='teacher', uselist=False, cascade="all, delete-orphan")


class UserAuth(db.Model):
    __tablename__ = 'user_auth'
    auth_id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), unique=True)
    hashed_password = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)