# controllers/teacher_controller.py
from flask import Blueprint, jsonify, request
from services.follow_service import FollowService 
from services.teacher_service import TeacherService
from lib.guards import verification_required 
from flask_jwt_extended import get_jwt_identity
from models  import db, Teacher, ResourceCollection, Quiz, QuizAttempt, ResourceLike, PostLike, ResourceComment, PostComment, UserActivity
import traceback

teacher_bp = Blueprint('teacher_controller', __name__)

@teacher_bp.route('/', methods=['GET'])
@verification_required
def get_all_teachers(current_teacher):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search')
        
        response_data = TeacherService.get_all_profiles(
            current_teacher.teacher_id, 
            page=page, 
            per_page=per_page,
            search=search
        )
        return jsonify({"success": True, **response_data}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/stats', methods=['GET'])
@verification_required
def get_dashboard_stats(current_teacher):
    try:
        days = request.args.get('days', 30, type=int)
        stats = TeacherService.get_dashboard_stats(current_teacher.teacher_id, days=days)
        return jsonify({"success": True, "data": stats}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/<int:teacher_id>', methods=['GET'])
@verification_required
def get_profile(current_teacher, teacher_id):
    try:
        profile = TeacherService.get_profile(teacher_id=teacher_id, current_user_id=current_teacher.teacher_id)
        if not profile:
            return jsonify({"error": True, "message": "Teacher not found"}), 404
        
        return jsonify({"success": True, "data": profile}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/u/<string:username>', methods=['GET'])
@verification_required
def get_profile_by_username(current_teacher, username):
    try:
        profile = TeacherService.get_profile(username=username, current_user_id=current_teacher.teacher_id)
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
        current_teacher.profile_image_url = data.get('profile_image_url', current_teacher.profile_image_url)
        
        # New Settings
        current_teacher.theme_preference = data.get('theme_preference', current_teacher.theme_preference)
        current_teacher.email_notifications = data.get('email_notifications', current_teacher.email_notifications)
        current_teacher.push_notifications = data.get('push_notifications', current_teacher.push_notifications)
        current_teacher.is_profile_public = data.get('is_profile_public', current_teacher.is_profile_public)
        current_teacher.show_email_on_profile = data.get('show_email_on_profile', current_teacher.show_email_on_profile)
        
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Profile updated successfully",
            "data": {
                "role": current_teacher.role,
                "institution": current_teacher.institution,
                "bio": current_teacher.bio,
                "profile_image_url": current_teacher.profile_image_url,
                "settings": {
                    "theme_preference": current_teacher.theme_preference,
                    "email_notifications": current_teacher.email_notifications,
                    "push_notifications": current_teacher.push_notifications,
                    "is_profile_public": current_teacher.is_profile_public,
                    "show_email_on_profile": current_teacher.show_email_on_profile
                }
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": True, "message": str(e)}), 500

@teacher_bp.route('/update/photo', methods=['POST'])
@verification_required
def upload_profile_photo(current_teacher):
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No selected file"}), 400

        from services.file_service import AppwriteService
        appwrite = AppwriteService()
        
        upload_result = appwrite.upload_file(file)
        
        current_teacher.profile_image_url = upload_result['url']
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Photo uploaded successfully",
            "url": upload_result['url']
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@teacher_bp.route('/<int:target_id>/follow', methods=['POST'])
@verification_required
def toggle_follow(current_teacher, target_id):
    try:
        current_user_id = current_teacher.teacher_id

        response_data, status_code = FollowService.toggle_follow(current_user_id, target_id)
        
        return jsonify(response_data), status_code

    except Exception as e:
        return jsonify({"error": True, "message": "An unexpected error occurred."}), 500

@teacher_bp.route('/<int:teacher_id>/activity', methods=['GET'])
@verification_required
def get_teacher_activity(current_teacher, teacher_id):
    try:
        from services.activity_service import ActivityService
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        result = ActivityService.get_user_activities(teacher_id, page, per_page)
        
        return jsonify({
            "success": True,
            **result
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@teacher_bp.route('/archive', methods=['POST'])
@verification_required
def archive_account(current_teacher):
    try:
        current_teacher.is_archived = True
        current_teacher.is_profile_public = False

        # Hide resources
        ResourceCollection.query.filter_by(owner_id=current_teacher.teacher_id).update({"visibility": "private"})

        db.session.commit()
        return jsonify({"success": True, "message": "Account archived successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
@teacher_bp.route('/restore', methods=['POST'])
@verification_required
def restore_account(current_teacher):
    try:
        current_teacher.is_archived = False
        db.session.commit()
        return jsonify({"success": True, "message": "Account restored successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@teacher_bp.route('/delete', methods=['DELETE'])
@verification_required
def delete_account(current_teacher):
    try:
        # 1. Clean up community interactions
        ResourceLike.query.filter_by(teacher_id=current_teacher.teacher_id).delete()
        PostLike.query.filter_by(teacher_id=current_teacher.teacher_id).delete()
        ResourceComment.query.filter_by(teacher_id=current_teacher.teacher_id).delete()
        PostComment.query.filter_by(teacher_id=current_teacher.teacher_id).delete()
        UserActivity.query.filter_by(teacher_id=current_teacher.teacher_id).delete()

        # 2. Delete Quizzes owned by user
        quizzes = Quiz.query.filter_by(teacher_id=current_teacher.teacher_id).all()
        for q in quizzes:
            db.session.delete(q)

        # 3. Delete Resources owned by user
        resources = ResourceCollection.query.filter_by(owner_id=current_teacher.teacher_id).all()
        for r in resources:
            db.session.delete(r)

        # Delete the teacher
        db.session.delete(current_teacher)
        db.session.commit()

        return jsonify({"success": True, "message": "Account deleted permanently"}), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

