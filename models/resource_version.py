from . import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB


class ResourceVersion(db.Model):
    __tablename__ = 'resource_version'
    
    version_id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    version_no = db.Column(db.Integer, nullable=False, default=1)
    
    # Snapshot Content
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(JSONB, nullable=True)
    
    notes = db.Column(db.Text, nullable=True) 
    is_latest = db.Column(db.Boolean, nullable=False, default=True)
    is_remix = db.Column(db.Boolean, nullable=False, default=False)
    
    # State Capture
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    visibility = db.Column(db.String(20), default='public', nullable=False) # 'public', 'private'
    
    # New metadata capture
    estimate_duration = db.Column(db.String(100), nullable=True)
    allow_remixing = db.Column(db.Boolean, default=True, nullable=False)
    collaboration_mode = db.Column(db.String(20), default='none', nullable=False) # 'none', 'invite_only'
    
    # Approval Workflow
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=True)
    
    # Citation Snapshot (for indestructible remixes)
    original_author_name = db.Column(db.String(255), nullable=True)
    original_author_username = db.Column(db.String(50), nullable=True)
    original_resource_title = db.Column(db.String(255), nullable=True)
    
    parent_version_id = db.Column(db.Integer, db.ForeignKey('resource_version.version_id', ondelete='SET NULL'), nullable=True)
    
    created_by = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    creator = db.relationship('Teacher', foreign_keys=[created_by])
    approved_by_teacher = db.relationship('Teacher', foreign_keys=[approved_by])
    files = db.relationship('ResourceFile', backref='version', lazy=True, cascade="all, delete-orphan")
    
    parent_version = db.relationship('ResourceVersion', remote_side=[version_id], backref='remixes')