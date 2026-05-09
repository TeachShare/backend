from . import db
from sqlalchemy.sql import func

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    notification_id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=True)
    
    # Type of notification: 'like', 'comment', 'download', 'remix', 'review'
    notification_type = db.Column(db.String(50), nullable=False)
    
    # Reference to the resource or entity involved
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=True)
    
    # Additional data (e.g. comment snippet, remix ID)
    extra_data = db.Column(db.JSON, nullable=True)
    
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    recipient = db.relationship('Teacher', foreign_keys=[recipient_id], backref='notifications_received')
    sender = db.relationship('Teacher', foreign_keys=[sender_id], backref='notifications_sent')
    collection = db.relationship('ResourceCollection', backref='notifications')
