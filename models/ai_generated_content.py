from . import db
from sqlalchemy.sql import func

class AIGeneratedContent(db.Model):
    __tablename__ = 'ai_generated_content'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(50), nullable=False) # lesson, strategy, classroom
    content_text = db.Column(db.Text, nullable=False)
    pdf_url = db.Column(db.String(500), nullable=True)
    subject = db.Column(db.String(100), nullable=True)
    grade_level = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    teacher = db.relationship('Teacher', backref='ai_contents')

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "type": self.content_type,
            "content": self.content_text,
            "pdf_url": self.pdf_url,
            "subject": self.subject,
            "grade": self.grade_level,
            "created_at": self.created_at.isoformat()
        }
