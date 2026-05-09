from . import db
from sqlalchemy.sql import func

class ResourceCollaborator(db.Model):
    __tablename__ = 'resource_collaborators'
    
    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    role = db.Column(db.String(20), default='editor', nullable=False) # 'editor', 'viewer'
    added_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    collection = db.relationship('ResourceCollection', backref=db.backref('collaborators', cascade="all, delete-orphan"))
    teacher = db.relationship('Teacher', backref='collaborating_on')
