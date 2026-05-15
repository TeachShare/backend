from . import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

class ResourceCollection(db.Model):
    __tablename__ = 'resource_collection'
    collection_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(JSONB, nullable=True)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id'), nullable=True)
    grade_level_id = db.Column(db.Integer, db.ForeignKey('grade_level.grade_level_id'), nullable=True)
    content_type_id = db.Column(db.Integer, db.ForeignKey('content_type.content_type_id'), nullable=True)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    estimate_duration = db.Column(db.String(100), nullable=True)
    student_summary = db.Column(db.Text, nullable=True)
    
    # Settings
    allow_remixing = db.Column(db.Boolean, default=True, nullable=False)
    visibility = db.Column(db.String(20), default='public', nullable=False) # 'public', 'private'
    collaboration_mode = db.Column(db.String(20), default='none', nullable=False) # 'none', 'invite_only'
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)

    owner = db.relationship('Teacher', backref='resources')
    subject = db.relationship('Subject', backref='resources')
    grade_level = db.relationship('GradeLevel', backref='resources')
    content_type = db.relationship('ContentType', backref='resources')