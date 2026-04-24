from . import db
from sqlalchemy.sql import func

class ResourceLike(db.Model):
    __tablename__ = 'resource_like'
    like_id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # Crucial: Prevent duplicate likes from the same person
    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'collection_id', name='_teacher_collection_like_uc'),
    )

    # Relationships for easier querying
    teacher = db.relationship('Teacher', backref='liked_resources')
    resource = db.relationship('ResourceCollection', backref='likes')