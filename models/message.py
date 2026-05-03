from . import db
from sqlalchemy.sql import func

class Message(db.Model):
    __tablename__ = 'messages'
    
    message_id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    sender = db.relationship('Teacher', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('Teacher', foreign_keys=[receiver_id], backref='received_messages')

    def to_dict(self):
        return {
            "id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat()
        }
