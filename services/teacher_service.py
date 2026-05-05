from models import Teacher, ResourceCollection, db, Follower
from sqlalchemy.sql import func

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

    @staticmethod
    def get_dashboard_stats(teacher_id):
        try:
            # Count the resources owned by this teacher
            resources_count = ResourceCollection.query.filter_by(owner_id=teacher_id).count()
            
            # Count records where this teacher is being followed
            followers_count = Follower.query.filter_by(followed_id=teacher_id).count()
            
            # Count records where this teacher is the one doing the following
            following_count = Follower.query.filter_by(follower_id=teacher_id).count()
            
            return {
                "total_resources": resources_count,
                "followers_count": followers_count,
                "following_count": following_count
            }
        except Exception as e:
            raise Exception(f"Failed to fetch dashboard stats: {str(e)}")

    @staticmethod
    def get_all_profiles(current_user_id, page=1, per_page=20):
        from models import Subject, GradeLevel
        
        # Get all teachers except current one with pagination
        pagination = Teacher.query.filter(Teacher.teacher_id != current_user_id).paginate(
            page=page, per_page=per_page, error_out=False
        )
        teachers = pagination.items
        
        teacher_ids = [t.teacher_id for t in teachers]
        if not teacher_ids:
            return {
                "teachers": [],
                "total_pages": pagination.pages,
                "current_page": pagination.page,
                "has_next": pagination.has_next
            }

        # Get current user's subjects/grades for alignment
        current_user_interests = db.session.query(
            ResourceCollection.subject_id, 
            ResourceCollection.grade_level_id
        ).filter(
            ResourceCollection.owner_id == current_user_id,
            ResourceCollection.is_published == True
        ).distinct().all()
        
        current_subjects = {s_id for s_id, g_id in current_user_interests if s_id}
        current_grades = {g_id for s_id, g_id in current_user_interests if g_id}
        
        # Pre-fetch counts for the paginated subset to keep it fast
        # Followers count
        followers_counts = dict(db.session.query(
            Follower.followed_id, func.count(Follower.follower_id)
        ).filter(Follower.followed_id.in_(teacher_ids)).group_by(Follower.followed_id).all())
        
        # Following count
        following_counts = dict(db.session.query(
            Follower.follower_id, func.count(Follower.followed_id)
        ).filter(Follower.follower_id.in_(teacher_ids)).group_by(Follower.follower_id).all())
        
        # Resources count
        resources_counts = dict(db.session.query(
            ResourceCollection.owner_id, func.count(ResourceCollection.collection_id)
        ).filter(
            ResourceCollection.owner_id.in_(teacher_ids),
            ResourceCollection.is_published == True
        ).group_by(ResourceCollection.owner_id).all())
        
        # Check if following
        following_ids = {f.followed_id for f in Follower.query.filter(
            Follower.follower_id == current_user_id,
            Follower.followed_id.in_(teacher_ids)
        ).all()}
        
        # Get tags for the paginated subset
        teacher_tags_query = db.session.query(
            ResourceCollection.owner_id,
            Subject.subject_name,
            GradeLevel.grade_name,
            ResourceCollection.subject_id,
            ResourceCollection.grade_level_id
        ).outerjoin(Subject, ResourceCollection.subject_id == Subject.subject_id)\
         .outerjoin(GradeLevel, ResourceCollection.grade_level_id == GradeLevel.grade_level_id)\
         .filter(
             ResourceCollection.owner_id.in_(teacher_ids),
             ResourceCollection.is_published == True
         ).all()
        
        teacher_tags_map = {} # teacher_id -> set of tags
        teacher_interests_map = {} # teacher_id -> (set of subject_ids, set of grade_level_ids)
        
        for owner_id, s_name, g_name, s_id, g_id in teacher_tags_query:
            if owner_id not in teacher_tags_map:
                teacher_tags_map[owner_id] = set()
                teacher_interests_map[owner_id] = (set(), set())
            if s_name: teacher_tags_map[owner_id].add(s_name)
            if g_name: teacher_tags_map[owner_id].add(g_name)
            if s_id: teacher_interests_map[owner_id][0].add(s_id)
            if g_id: teacher_interests_map[owner_id][1].add(g_id)

        data = []
        for t in teachers:
            t_id = t.teacher_id
            
            # Calculate alignment
            alignment = 0
            if current_subjects or current_grades:
                t_subjects, t_grades = teacher_interests_map.get(t_id, (set(), set()))
                match_count = len(current_subjects & t_subjects) + len(current_grades & t_grades)
                total_interests = len(current_subjects | t_subjects) + len(current_grades | t_grades)
                
                if total_interests > 0:
                    alignment = int((match_count / total_interests) * 100)
                    alignment = min(100, alignment + 40) if match_count > 0 else 20
                else:
                    alignment = 50 
            else:
                alignment = 60 
            
            data.append({
                "id": t_id,
                "first_name": t.first_name,
                "last_name": t.last_name,
                "profile_image_url": t.profile_image_url,
                "role": t.role,
                "institution": t.institution,
                "is_verified": t.is_verified,
                "is_following": t_id in following_ids,
                "tags": list(teacher_tags_map.get(t_id, set()))[:3],
                "alignment": alignment,
                "stats": {
                    "followers": followers_counts.get(t_id, 0),
                    "following": following_counts.get(t_id, 0),
                    "resources": resources_counts.get(t_id, 0)
                }
            })
            
        return {
            "teachers": data,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next
        }