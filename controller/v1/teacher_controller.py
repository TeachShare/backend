# controllers/teacher_controller.py
from flask import Blueprint, jsonify, request
from services.follow_service import FollowService 
from services.teacher_service import TeacherService
from lib.guards import verification_required 
from flask_jwt_extended import get_jwt_identity
from models  import db

teacher_bp = Blueprint('teacher_controller', __name__)

@teacher_bp.route('/', methods=['GET'])
@verification_required
def get_all_teachers(current_teacher):
    try:
        teachers = Teacher.query.filter(Teacher.teacher_id != current_teacher.teacher_id).all()
        
        data = []
        for t in teachers:
            profile = TeacherService.get_profile(t.teacher_id, current_user_id=current_teacher.teacher_id)
            data.append(profile)
            
        return jsonify({"success": True, "data": data}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/<int:teacher_id>', methods=['GET'])
@verification_required
def get_profile(current_teacher, teacher_id):
    try:
        profile = TeacherService.get_profile(teacher_id, current_user_id=current_teacher.teacher_id)
        if not profile:
            return jsonify({"error": True, "message": "Teacher not found"}), 404
        
        return jsonify({"success": True, "data": profile}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/<int:teacher_id>/resources', methods=['GET'])
@verification_required
def get_teacher_resources(current_teacher, teacher_id):
    try:
        resources = TeacherService.get_teacher_resources(teacher_id)
        return jsonify({"success": True, "data": resources}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/update', methods=['PUT'])
@verification_required
def update_profile(current_teacher):
    try:
        data = request.get_json()
        
        current_teacher.role = data.get('role', current_teacher.role)
        current_teacher.institution = data.get('institution', current_teacher.institution)
        current_teacher.bio = data.get('bio', current_teacher.bio)
        
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Profile updated successfully",
            "data": {
                "role": current_teacher.role,
                "institution": current_teacher.institution,
                "bio": current_teacher.bio
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/<int:target_id>/follow', methods=['POST'])
@verification_required
def toggle_follow(current_teacher, target_id):
    try:
        current_user_id = current_teacher.teacher_id

        response_data, status_code = FollowService.toggle_follow(current_user_id, target_id)
        
        return jsonify(response_data), status_code

    except Exception as e:
        return jsonify({"error": True, "message": "An unexpected error occurred."}), 500