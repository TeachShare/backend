from . import db
from sqlalchemy.sql import func

class ResourceRating(db.Model):
    __tablename__ = 'resource_rating'
    rating_id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())

    # --- ADD THESE LINES ---
    teacher = db.relationship('Teacher', backref='ratings')
    collection = db.relationship('ResourceCollection', backref='ratings_list')