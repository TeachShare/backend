from models import UserActivity, db, Teacher, ResourceCollection
from datetime import datetime, timezone

class ActivityService:
    @staticmethod
    def log_activity(user_id, activity_type, collection_id=None, target_user_id=None, extra_data=None):
        try:
            new_activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                collection_id=collection_id,
                target_user_id=target_user_id,
                extra_data=extra_data
            )
            db.session.add(new_activity)
            db.session.commit()
            return new_activity
        except Exception as e:
            db.session.rollback()
            print(f"Error logging activity: {e}")
            return None

    @staticmethod
    def get_user_activities(user_id, page=1, per_page=20):
        pagination = UserActivity.query.filter_by(user_id=user_id)\
            .order_by(UserActivity.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            "activities": [ActivityService.format_activity(a) for a in pagination.items],
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next
        }

    @staticmethod
    def format_activity(a):
        return {
            "id": a.activity_id,
            "type": a.activity_type,
            "collection_id": a.collection_id,
            "collection_title": a.collection.title if a.collection else None,
            "target_user_id": a.target_user_id,
            "target_user_name": f"{a.target_user.first_name} {a.target_user.last_name}" if a.target_user else None,
            "extra_data": a.extra_data,
            "created_at": a.created_at.isoformat(),
            "description": ActivityService.get_activity_text(a)
        }

    @staticmethod
    def get_activity_text(a):
        t = a.activity_type
        title = a.collection.title if a.collection else "a resource"
        target_name = f"{a.target_user.first_name} {a.target_user.last_name}" if a.target_user else "a user"
        
        if t == 'post_resource':
            return f"Published {title}"
        elif t == 'like_resource':
            return f"Liked {title}"
        elif t == 'comment_resource':
            return f"Commented on {title}"
        elif t == 'remix_resource':
            return f"Remixed {title}"
        elif t == 'follow_user':
            return f"Started following {target_name}"
        elif t == 'review_resource':
            return f"Reviewed {title}"
        elif t == 'update_resource':
            return f"Updated {title}"
        
        return "Interacted with the platform"
