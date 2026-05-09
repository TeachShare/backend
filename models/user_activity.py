from . import db
from sqlalchemy.sql import func

class UserActivity(db.Model):
    __tablename__ = 'user_activities'
    
    activity_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    
    # Type of activity: 'post_resource', 'like_resource', 'comment_resource', 'remix_resource', 'follow_user'
    activity_type = db.Column(db.String(50), nullable=False)
    
    # Reference to the resource involved
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=True)
    
    # Reference to another user (e.g. if following)
    target_user_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=True)
    
    # Additional info (e.g. resource title, comment snippet)
    extra_data = db.Column(db.JSON, nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    user = db.relationship('Teacher', foreign_keys=[user_id], backref='activities')
    target_user = db.relationship('Teacher', foreign_keys=[target_user_id], backref='targeted_activities')
    collection = db.relationship('ResourceCollection', backref='activities')
