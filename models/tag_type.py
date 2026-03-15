from . import db

class TagType(db.Model):
    __tablename__ = 'tag_type'
    tag_type_id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(50), nullable=False, unique=True)
