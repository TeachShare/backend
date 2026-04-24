from models import db, ResourceRating, ResourceComment, ResourceLike

class InteractionService:
    @staticmethod
    def add_review(collection_id, teacher_id, data):
        score = data.get('rating')
        content = data.get('text')
        
        if score:
            rating = ResourceRating.query.filter_by(
                collection_id=collection_id, 
                teacher_id=teacher_id
            ).first()
            
            if rating:
                rating.score = score
            else:
                rating = ResourceRating(
                    collection_id=collection_id,
                    teacher_id=teacher_id,
                    score=score
                )
                db.session.add(rating)

        new_comment = None
        if content and content.strip():
            new_comment = ResourceComment(
                collection_id=collection_id,
                teacher_id=teacher_id,
                content=content
            )
            db.session.add(new_comment)

        db.session.commit()

        if new_comment:
            return {
                "id": new_comment.comment_id,
                "user": f"{new_comment.teacher.first_name} {new_comment.teacher.last_name}",
                "avatar": new_comment.teacher.first_name[0],
                "rating": score, 
                "text": new_comment.content,
                "date": "Just now"
            }
        return None
    
    @staticmethod
    def toggle_like(collection_id, teacher_id):
        existing_like = ResourceLike.query.filter_by(
            collection_id=collection_id, 
            teacher_id=teacher_id
        ).first()

        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()
            return {"liked": False, "message": "Like removed"}
        else:
            new_like = ResourceLike(
                collection_id=collection_id,
                teacher_id=teacher_id
            )
            db.session.add(new_like)
            db.session.commit()
            return {"liked": True, "message": "Resource liked"}