from models import Teacher, ResourceCollection, db, Follower
from sqlalchemy.sql import func
from sqlalchemy import or_

class TeacherService:
    @staticmethod
    def get_profile(teacher_id=None, username=None, current_user_id=None):
        if teacher_id:
            teacher = Teacher.query.get(teacher_id)
        elif username:
            teacher = Teacher.query.filter_by(username=username).first()
        else:
            return None

        if not teacher:
            return None
        
        teacher_id = teacher.teacher_id # Ensure we have the ID for queries
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
            "username": teacher.username,
            "first_name": teacher.first_name,
            "last_name": teacher.last_name,
            "email": teacher.email,
            "profile_image_url": teacher.profile_image_url,
            "cover_image_url": teacher.cover_image_url,
            "auth_provider": teacher.auth.auth_provider if teacher.auth else "local",
            "role": teacher.role,
            "institution": teacher.institution,
            "bio": teacher.bio,
            "is_verified": teacher.is_verified,
            "is_following": is_following,
            "joined_date": teacher.joined_date.isoformat(),
            "settings": {
                "theme_preference": teacher.theme_preference,
                "email_notifications": teacher.email_notifications,
                "push_notifications": teacher.push_notifications,
                "is_profile_public": teacher.is_profile_public,
                "show_email_on_profile": teacher.show_email_on_profile
            },
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
    def get_dashboard_stats(teacher_id, days=30):
        try:
            from models import ResourceCollection, Follower, ResourceLike
            from datetime import datetime, timezone, timedelta
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            teacher = Teacher.query.get(teacher_id)
            if not teacher:
                raise Exception("Teacher not found")

            # Resources counts
            total_resources = ResourceCollection.query.filter_by(owner_id=teacher_id, is_hidden=False).count()
            published_count = ResourceCollection.query.filter_by(owner_id=teacher_id, is_published=True, is_hidden=False).count()
            draft_count = total_resources - published_count
            
            # Growth in period
            period_resources = ResourceCollection.query.filter(
                ResourceCollection.owner_id == teacher_id,
                ResourceCollection.created_at >= start_date
            ).count()

            # Likes counts
            total_likes = db.session.query(func.count(ResourceLike.like_id))\
                .join(ResourceCollection, ResourceLike.collection_id == ResourceCollection.collection_id)\
                .filter(ResourceCollection.owner_id == teacher_id).scalar() or 0
            
            period_likes = db.session.query(func.count(ResourceLike.like_id))\
                .join(ResourceCollection, ResourceLike.collection_id == ResourceCollection.collection_id)\
                .filter(ResourceCollection.owner_id == teacher_id)\
                .filter(ResourceLike.created_at >= start_date).scalar() or 0

            # Followers
            followers_count = Follower.query.filter_by(followed_id=teacher_id).count()
            following_count = Follower.query.filter_by(follower_id=teacher_id).count()

            # Roadmap Stats (Certification)
            profile_completion = 0
            if teacher.bio: profile_completion += 25
            if teacher.institution: profile_completion += 25
            if teacher.role: profile_completion += 25
            if teacher.profile_image_url: profile_completion += 25
            
            roadmap = {
                "profile_complete": profile_completion == 100,
                "profile_completion_percentage": profile_completion,
                "resources_published": published_count,
                "resources_goal": 5,
                "likes_received": total_likes,
                "likes_goal": 10,
                "is_verified": teacher.is_verified
            }
            
            return {
                "total_resources": total_resources,
                "published_count": published_count,
                "draft_count": draft_count,
                "period_resources": period_resources,
                "total_likes": total_likes,
                "period_likes": period_likes,
                "followers_count": followers_count,
                "following_count": following_count,
                "roadmap": roadmap
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to fetch dashboard stats: {str(e)}")

    @staticmethod
    def get_all_profiles(current_user_id, page=1, per_page=20, search=None):
        from models import Subject, GradeLevel
        
        query = Teacher.query.filter(Teacher.teacher_id != current_user_id)
        
        if search:
            search_query = f"%{search}%"
            query = query.filter(
                or_(
                    Teacher.username.ilike(search_query),
                    Teacher.first_name.ilike(search_query),
                    Teacher.last_name.ilike(search_query),
                    Teacher.email.ilike(search_query)
                )
            )

        # Get all teachers except current one with pagination
        pagination = query.paginate(
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
                "username": t.username,
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