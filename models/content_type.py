from . import db

class ContentType(db.Model):
    __tablename__ = 'content_type'
    content_type_id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(50), nullable=False, unique=True)