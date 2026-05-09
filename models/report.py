from . import db
from sqlalchemy.sql import func

class Report(db.Model):
    __tablename__ = 'reports'

    report_id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    
    # Polymorphic-like target identification
    target_type = db.Column(db.String(50), nullable=False) # 'resource', 'comment', 'post', 'teacher'
    target_id = db.Column(db.Integer, nullable=False)
    
    reason = db.Column(db.String(50), nullable=False) # 'inappropriate', 'spam', 'copyright', 'other'
    description = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(20), default='pending') # 'pending', 'reviewed', 'resolved', 'dismissed'
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    # Relationships
    reporter = db.relationship('Teacher', foreign_keys=[reporter_id], backref='reports_submitted')

    def to_dict(self):
        return {
            "report_id": self.report_id,
            "reporter_id": self.reporter_id,
            "reporter_name": f"{self.reporter.first_name} {self.reporter.last_name}" if self.reporter else "Unknown",
            "target_type": self.target_type,
            "target_id": self.target_id,
            "reason": self.reason,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
