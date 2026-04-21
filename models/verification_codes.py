from . import db
from sqlalchemy.sql import func
from datetime import datetime, timedelta

class VerificationCodes(db.Model):
    __tablename__ = 'verification_codes'
    verification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    expires_at = db.Column(
        db.DateTime,
        default = lambda: datetime.utcnow() + timedelta(minutes=10)
    )

    teacher = db.relationship('Teacher', backref=db.backref('verification_codes', lazy=True))