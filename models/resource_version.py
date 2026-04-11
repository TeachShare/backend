from . import db
from sqlalchemy.sql import func


class ResourceVersion(db.Model):
    __tablename__ = 'resource_version'
    
    version_id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    version_no = db.Column(db.Integer, nullable=False, default=1)
    notes = db.Column(db.Text, nullable=True) 
    is_latest = db.Column(db.Boolean, nullable=False, default=True)
    is_remix = db.Column(db.Boolean, nullable=False, default=False)
    
    parent_version_id = db.Column(db.Integer, db.ForeignKey('resource_version.version_id'), nullable=True)
    
    created_by = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    files = db.relationship('ResourceFile', backref='version', lazy=True, cascade="all, delete-orphan")
    
    parent_version = db.relationship('ResourceVersion', remote_side=[version_id], backref='remixes')