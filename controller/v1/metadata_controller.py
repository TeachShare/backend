from flask import Blueprint, jsonify
from models import Teacher, ResourceCollection, AIGeneratedContent, Follower, Subject, GradeLevel, ContentType, db
from lib.guards import verification_required
from sqlalchemy import func

metadata_bp = Blueprint('metadata_controller', __name__)

@metadata_bp.get('/form-options')
@metadata_bp.get('/metadata/form-options') # Legacy compatibility
def get_form_options():
    try:
        subjects = Subject.query.order_by(Subject.rank.asc(), Subject.subject_name.asc()).all()
        grade_levels = GradeLevel.query.order_by(GradeLevel.rank.asc()).all()
        content_types = ContentType.query.order_by(ContentType.type_name.asc()).all()

        return jsonify({
            "success": True,
            "data": {
                "subjects": [{"id": s.subject_id, "name": s.subject_name} for s in subjects],
                "grade_levels": [{"id": g.grade_level_id, "name": g.grade_name} for g in grade_levels],
                "content_types": [{"id": c.content_type_id, "name": c.type_name} for c in content_types]
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@metadata_bp.get('/dashboard-stats')
@verification_required
def get_dashboard_stats(current_teacher):
    try:
        teacher_id = current_teacher.teacher_id

        # 1. Total Resources Shared
        resources_count = ResourceCollection.query.filter_by(owner_id=teacher_id).count()

        # 2. AI Content Generated
        ai_count = AIGeneratedContent.query.filter_by(teacher_id=teacher_id).count()

        # 3. Followers Count
        followers_count = Follower.query.filter_by(following_id=teacher_id).count()

        # 4. Following Count
        following_count = Follower.query.filter_by(follower_id=teacher_id).count()

        # 5. Recent Resources (last 4)
        recent_resources = ResourceCollection.query.filter_by(owner_id=teacher_id)\
            .order_by(ResourceCollection.created_at.desc())\
            .limit(4).all()

        recent_resources_data = []
        for r in recent_resources:
            recent_resources_data.append({
                "id": r.collection_id,
                "title": r.title,
                "subject": r.subject.name if r.subject else "General",
                "grade": r.grade_level.name if r.grade_level else "N/A",
                "created_at": r.created_at.isoformat()
            })

        # 6. Recent AI Content (last 3)
        recent_ai = AIGeneratedContent.query.filter_by(teacher_id=teacher_id)\
            .order_by(AIGeneratedContent.created_at.desc())\
            .limit(3).all()
        
        recent_ai_data = []
        for ai in recent_ai:
            recent_ai_data.append({
                "id": ai.id,
                "title": ai.title,
                "type": ai.content_type,
                "created_at": ai.created_at.isoformat()
            })

        return jsonify({
            "success": True,
            "data": {
                "stats": {
                    "resources_shared": resources_count,
                    "ai_generated": ai_count,
                    "followers": followers_count,
                    "following": following_count
                },
                "recent_resources": recent_resources_data,
                "recent_ai": recent_ai_data
            }
        }), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500
