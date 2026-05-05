# controllers/teacher_controller.py
from flask import Blueprint, jsonify, request
from services.follow_service import FollowService 
from services.teacher_service import TeacherService
from lib.guards import verification_required 
from flask_jwt_extended import get_jwt_identity
from models  import db, Teacher
import traceback

teacher_bp = Blueprint('teacher_controller', __name__)

@teacher_bp.route('/', methods=['GET'])
@verification_required
def get_all_teachers(current_teacher):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        response_data = TeacherService.get_all_profiles(
            current_teacher.teacher_id, 
            page=page, 
            per_page=per_page
        )
        return jsonify({"success": True, **response_data}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/stats', methods=['GET'])
@verification_required
def get_dashboard_stats(current_teacher):
    try:
        stats = TeacherService.get_dashboard_stats(current_teacher.teacher_id)
        return jsonify({"success": True, "data": stats}), 200
    except Exception as e:
        traceback.print_exc()
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