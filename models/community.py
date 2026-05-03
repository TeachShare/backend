from . import db
from sqlalchemy.sql import func

class CommunityPost(db.Model):
    __tablename__ = 'community_posts'
    
    post_id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    
    content = db.Column(db.Text, nullable=False)
    
    linked_resource_id = db.Column(db.Integer, db.ForeignKey('resource_collection.collection_id'), nullable=True) 
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    author = db.relationship('Teacher', backref=db.backref('post_comments', lazy='dynamic'))
    likes = db.relationship('PostLike', backref='post', lazy='dynamic', cascade="all, delete-orphan")
    
    # This relationship defines 'comments' on the CommunityPost
    comments = db.relationship('PostComment', backref='post', lazy='dynamic', cascade="all, delete-orphan")
    
    linked_resource = db.relationship('ResourceCollection', backref='community_shares')

class PostLike(db.Model):
    __tablename__ = 'post_likes'
    
    like_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.post_id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (db.UniqueConstraint('post_id', 'teacher_id', name='_post_teacher_uc'),)


class PostComment(db.Model):
    __tablename__ = 'post_comments'
    
    comment_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.post_id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    
    parent_id = db.Column(db.Integer, db.ForeignKey('post_comments.comment_id'), nullable=True)
    
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    # UPDATED: Renamed backref to prevent collision with CommunityPost
    author = db.relationship('Teacher', backref=db.backref('authored_comments', lazy='dynamic'))
    
    replies = db.relationship(
        'PostComment', 
        backref=db.backref('parent', remote_side=[comment_id]),
        lazy='dynamic',
        cascade="all, delete-orphan"
    )