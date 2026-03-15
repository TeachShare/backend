from . import db

class Tag(db.Model):
    __tablename__ = 'tag'
    tag_id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(50), nullable=False, unique=True)

    tag_type_id = db.Column(db.Integer, db.ForeignKey('tag_type.tag_type_id'), nullable=False)
    tag_type = db.relationship('TagType', backref='tags')