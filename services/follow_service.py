from models import db, Teacher 

class FollowService:
    
    @staticmethod
    def is_following(follower, followed):
        """Helper to check the relationship status directly through the Teacher model"""
        return follower.followed.filter_by(teacher_id=followed.teacher_id).first() is not None

    @staticmethod
    def toggle_follow(follower_id, followed_id):
        if follower_id == followed_id:
            return {"error": True, "message": "You cannot follow yourself"}, 400

        follower = Teacher.query.get(follower_id)
        followed = Teacher.query.get(followed_id)

        if not follower or not followed:
            return {"error": True, "message": "Teacher not found"}, 404

        if FollowService.is_following(follower, followed):
            follower.followed.remove(followed)
            db.session.commit()
            return {"following": False, "message": f"You unfollowed {followed.first_name}"}, 200
        else:
            follower.followed.append(followed)
            db.session.commit()

            # Log Activity
            from services.activity_service import ActivityService
            ActivityService.log_activity(
                user_id=follower_id,
                activity_type='follow_user',
                target_user_id=followed_id
            )

            return {"following": True, "message": f"You are now following {followed.first_name}"}, 200