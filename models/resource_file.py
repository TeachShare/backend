from . import db

class ResourceFile(db.Model):
    __tablename__ = 'resource_file'
    
    file_id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('resource_version.version_id'), nullable=False)
    
    file_url = db.Column(db.String(500), nullable=False)  
    file_name = db.Column(db.String(255), nullable=False) 
    file_type = db.Column(db.String(100), nullable=True)  
    
    file_size = db.Column(db.Integer, nullable=True)
    file_hash = db.Column(db.String(64), nullable=True, index=True)