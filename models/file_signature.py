from . import db
from sqlalchemy.sql import func

class FileSignature(db.Model):
    __tablename__ = 'file_signatures'
    
    id = db.Column(db.Integer, primary_key=True)
    file_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    file_url = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
