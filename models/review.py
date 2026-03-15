from . import db
from sqlalchemy.sql import func

class Review(db.Model):
    __tablename__ = 'review'
    review_id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    review_by = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)


    __table_args__ = (
        db.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
    )

    resource = db.relationship('ResourceCollection', backref=db.backref('reviews', cascade="all, delete-orphan"))
    reviewer=  db.relationship('Teacher', backref='reviews_written')