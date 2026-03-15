from . import db

class ResourceTag(db.Model):
    __tablename__ = 'resource_tag'
    resource_tag_id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.tag_id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('collection_id', 'tag_id', name='_collection_tag_uc'),
    )

    resource = db.relationship('ResourceCollection', backref=db.backref('resource_tags', cascade='all, delete-orphan'))
    tag = db.relationship('Tag', backref='resource_tags')