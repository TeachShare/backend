from flask import Blueprint, jsonify
from models import Subject, GradeLevel, ContentType

metadata_bp = Blueprint('metadata', __name__)

@metadata_bp.route('/form-options', methods=['GET'])
def get_form_options():
    try:
        subjects = Subject.query.all()
        grades = GradeLevel.query.all()
        content_types = ContentType.query.all()

        return jsonify({
            "success": True,
            "data": {
                "subjects": [{"id": s.subject_id, "name": s.subject_name} for s in subjects],
                "grade_levels": [{"id": g.grade_level_id, "name": g.grade_name} for g in grades],
                "content_types": [{"id": c.content_type_id, "name": c.type_name} for c in content_types]
            }
        }), 200
    except Exception as e:
        print(f"Error fetching metada: {e}")
        return jsonify({"success": False, "error": "Failed to load form options"}), 500
    