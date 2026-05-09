from . import db
from sqlalchemy.sql import func

class ResourceComment(db.Model):
    __tablename__ = 'resource_comment'
    comment_id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)

    teacher = db.relationship('Teacher', backref='comments')
    collection = db.relationship('ResourceCollection', backref='comments_list')