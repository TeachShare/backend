from . import db
from sqlalchemy.sql import func

class Follower(db.Model):
    __tablename__ = 'followers'
    
    follower_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), primary_key=True)
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)