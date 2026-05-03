from . import db
from sqlalchemy.sql import func

class Teacher(db.Model):
    __tablename__ = 'teachers'
    teacher_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)

    profile_image_url = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(100), nullable=True)
    institution = db.Column(db.String(150), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    joined_date = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    auth = db.relationship('UserAuth', backref='teacher', uselist=False, cascade="all, delete-orphan")

    followed = db.relationship(
        'Teacher', 
        secondary='followers', 
        primaryjoin='Teacher.teacher_id == followers.c.follower_id',
        secondaryjoin='Teacher.teacher_id == followers.c.followed_id',
        backref=db.backref('followers', lazy='dynamic'),
        lazy='dynamic'
    )


class UserAuth(db.Model):
    __tablename__ = 'user_auth'
    auth_id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), unique=True, nullable=False)
    hashed_password = db.Column(db.Text, nullable=True)

    google_id = db.Column(db.String(255), unique=True, nullable=True)
    auth_provider = db.Column(db.String(20), nullable=False, default="local")

    is_active = db.Column(db.Boolean, default=True)