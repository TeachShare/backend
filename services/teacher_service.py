from models import Teacher, ResourceCollection, db

class TeacherService:
    @staticmethod
    def get_profile(teacher_id, current_user_id=None):
        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            return None
        
        followers_count = teacher.followers.count()
        following_count = teacher.followed.count()
        resources_count = ResourceCollection.query.filter_by(owner_id=teacher_id, is_published=True).count()

        is_following = False
        if current_user_id:
            from services.follow_service import FollowService
            current_user = Teacher.query.get(current_user_id)
            if current_user:
                is_following = FollowService.is_following(current_user, teacher)

        return {
            "id": teacher.teacher_id,
            "first_name": teacher.first_name,
            "last_name": teacher.last_name,
            "email": teacher.email,
            "profile_image_url": teacher.profile_image_url,
            "role": teacher.role,
            "institution": teacher.institution,
            "bio": teacher.bio,
            "is_verified": teacher.is_verified,
            "is_following": is_following,
            "joined_date": teacher.joined_date.isoformat(),
            "stats": {
                "followers": followers_count,
                "following": following_count,
                "resources": resources_count
            }
        }

    @staticmethod
    def get_teacher_resources(teacher_id):
        from services.resource_collection_service import ResourceCollectionService
        # We can reuse get_my_resources but with public filters
        filters = {"status": "published"}
        return ResourceCollectionService.get_my_resources(teacher_id, filters)
