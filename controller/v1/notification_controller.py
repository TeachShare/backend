from flask import Blueprint, jsonify, request
from services.notification_service import NotificationService
from lib import verification_required

notification_bp = Blueprint('notification', __name__)

@notification_bp.route('/', methods=['GET'])
@verification_required
def get_notifications(current_teacher):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        result = NotificationService.get_user_notifications(current_teacher.teacher_id, page, per_page)
        
        return jsonify({
            "success": True,
            **result
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@notification_bp.route('/mark-read/<int:notification_id>', methods=['POST'])
@verification_required
def mark_read(current_teacher, notification_id):
    try:
        success = NotificationService.mark_as_read(notification_id, current_teacher.teacher_id)
        return jsonify({"success": success}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@notification_bp.route('/mark-all-read', methods=['POST'])
@verification_required
def mark_all_read(current_teacher):
    try:
        success = NotificationService.mark_all_as_read(current_teacher.teacher_id)
        return jsonify({"success": success}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
