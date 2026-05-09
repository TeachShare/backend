from models import db, Teacher 
from models import CommunityPost, PostLike, PostComment

class CommunityService:

    @staticmethod
    def create_post(teacher_id, data):
        content = data.get('content')
        linked_resource_id = data.get('linked_resource_id')

        if not content or not content.strip():
            return {"error": True, "message": "Post content cannot be empty"}, 400

        # Prevent foreign key violations by sanitizing invalid resource IDs
        if linked_resource_id in [0, "0", "", None]:
            linked_resource_id = None
        else:
            try:
                linked_resource_id = int(linked_resource_id)
            except (ValueError, TypeError):
                linked_resource_id = None

        new_post = CommunityPost(
            teacher_id=teacher_id,
            content=content.strip(),
            linked_resource_id=linked_resource_id
        )

        db.session.add(new_post)
        db.session.commit()

        return {
            "success": True, 
            "message": "Post published successfully",
            "post_id": new_post.post_id
        }, 201

    @staticmethod
    def get_feed(current_teacher_id, page=1, per_page=20):
        # We can use 'joinedload' to fetch the resource in the same database query, 
        # preventing the "N+1 query problem" and keeping your app blazing fast.
        from sqlalchemy.orm import joinedload
        
        pagination = CommunityPost.query.options(
            joinedload(CommunityPost.linked_resource)
        ).filter(CommunityPost.is_hidden == False).order_by(CommunityPost.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        posts_data = []
        for post in pagination.items:
            author = post.author
            user_liked = post.likes.filter_by(teacher_id=current_teacher_id).first() is not None

            # Format the linked resource if it exists
            resource_data = None
            if post.linked_resource:
                resource = post.linked_resource
                resource_data = {
                    "id": resource.collection_id,
                    "title": resource.title,
                }

            posts_data.append({
                "id": post.post_id,
                "content": post.content,
                "created_at": post.created_at.isoformat(),
                "linked_resource": resource_data, 
                "author": {
                    "id": author.teacher_id,
                    "username": author.username,
                    "name": f"{author.first_name} {author.last_name}",
                    "avatar": author.profile_image_url
                },
                "engagement": {
                    "likes_count": post.likes.count(),
                    "comments_count": post.comments.count(),
                    "user_has_liked": user_liked
                }
            })

        return {
            "posts": posts_data,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next
        }, 200

    @staticmethod
    def toggle_like(teacher_id, post_id):
        post = CommunityPost.query.get(post_id)
        if not post:
            return {"error": True, "message": "Post not found"}, 404

        existing_like = PostLike.query.filter_by(post_id=post_id, teacher_id=teacher_id).first()

        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()
            return {"liked": False, "message": "Like removed"}, 200
        else:
            new_like = PostLike(post_id=post_id, teacher_id=teacher_id)
            db.session.add(new_like)
            db.session.commit()
            return {"liked": True, "message": "Post liked"}, 200

    @staticmethod
    def add_comment(teacher_id, post_id, data):
        content = data.get('content')
        parent_id = data.get('parent_id') 

        if not content or not content.strip():
            return {"error": True, "message": "Comment cannot be empty"}, 400

        post = CommunityPost.query.get(post_id)
        if not post:
            return {"error": True, "message": "Post not found"}, 404

        if parent_id:
            parent_comment = PostComment.query.get(parent_id)
            if not parent_comment or parent_comment.post_id != post_id:
                return {"error": True, "message": "Invalid parent comment"}, 400

        new_comment = PostComment(
            teacher_id=teacher_id,
            post_id=post_id,
            parent_id=parent_id,
            content=content.strip()
        )

        db.session.add(new_comment)
        db.session.commit()

        return {
            "success": True, 
            "message": "Comment posted",
            "comment": {
                "id": new_comment.comment_id,
                "parent_id": new_comment.parent_id,
                "content": new_comment.content
            }
        }, 201

    @staticmethod
    def get_post_comments(post_id):
        post = CommunityPost.query.get(post_id)
        if not post:
            return {"error": True, "message": "Post not found"}, 404

        all_comments = PostComment.query.filter_by(post_id=post_id, is_hidden=False).order_by(PostComment.created_at.asc()).all()
        
        return {"comments": CommunityService._build_comment_tree(all_comments)}, 200

    @staticmethod
    def _build_comment_tree(comments):
        comment_dict = {}
        tree = []

        for comment in comments:
            author = comment.author
            comment_dict[comment.comment_id] = {
                "id": comment.comment_id,
                "content": comment.content,
                "created_at": comment.created_at.isoformat(),
                "author": {
                    "id": author.teacher_id,
                    "username": author.username,
                    "name": f"{author.first_name} {author.last_name}",
                    "avatar": author.profile_image_url
                },
                "replies": [] 
            }

        for comment in comments:
            if comment.parent_id:
                if comment.parent_id in comment_dict:
                    comment_dict[comment.parent_id]["replies"].append(comment_dict[comment.comment_id])
            else:
                tree.append(comment_dict[comment.comment_id])

        return tree