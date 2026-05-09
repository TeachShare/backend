from models import db, ResourceRating, ResourceComment, ResourceLike, ResourceCollection
from services.notification_service import NotificationService
from services.activity_service import ActivityService

class InteractionService:
    @staticmethod
    def add_review(collection_id, teacher_id, data):
        score = data.get('rating')
        content = data.get('text')
        
        resource = ResourceCollection.query.get(collection_id)
        if not resource:
            raise ValueError("Resource not found")

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

        # Trigger Notification for review/comment
        notif_type = 'review' if score and not content else 'comment'
        NotificationService.create_notification(
            recipient_id=resource.owner_id,
            notification_type=notif_type,
            sender_id=teacher_id,
            collection_id=collection_id,
            extra_data={"text": content} if content else None
        )

        # Log Activity
        act_type = 'review_resource' if score and not content else 'comment_resource'
        ActivityService.log_activity(
            user_id=teacher_id,
            activity_type=act_type,
            collection_id=collection_id,
            extra_data={"text": content[:50] + "..." if content and len(content) > 50 else content}
        )

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
        resource = ResourceCollection.query.get(collection_id)
        if not resource:
            raise ValueError("Resource not found")

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

            # Trigger Notification for like
            NotificationService.create_notification(
                recipient_id=resource.owner_id,
                notification_type='like',
                sender_id=teacher_id,
                collection_id=collection_id
            )

            # Log Activity
            ActivityService.log_activity(
                user_id=teacher_id,
                activity_type='like_resource',
                collection_id=collection_id
            )

            return {"liked": True, "message": "Resource liked"}

    @staticmethod
    def increment_download_count(collection_id, downloader_id=None):
        resource = ResourceCollection.query.get(collection_id)
        if not resource:
            raise ValueError("Resource not found")
        
        resource.download_count += 1
        db.session.commit()

        # Trigger Notification for download
        if downloader_id:
            NotificationService.create_notification(
                recipient_id=resource.owner_id,
                notification_type='download',
                sender_id=downloader_id,
                collection_id=collection_id
            )

        return resource.download_count