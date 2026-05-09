from flask import Blueprint, jsonify, request
from services.moderation_service import ModerationService
from lib.guards import verification_required, admin_required
import traceback

moderation_bp = Blueprint('moderation_controller', __name__)

@moderation_bp.route('/report', methods=['POST'])
@verification_required
def report_content_route(current_teacher):
    try:
        data = request.get_json()
        target_type = data.get('target_type') # 'resource', 'comment', 'post', 'teacher'
        target_id = data.get('target_id')
        reason = data.get('reason')
        description = data.get('description')

        if not all([target_type, target_id, reason]):
            return jsonify({"success": False, "error": "target_type, target_id, and reason are required"}), 400

        report = ModerationService.create_report(
            reporter_id=current_teacher.teacher_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            description=description
        )

        return jsonify({
            "success": True, 
            "message": "Report submitted successfully. Our moderators will review it shortly.",
            "report_id": report.report_id
        }), 201

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": "Internal server error"}), 500

@moderation_bp.route('/admin/reports', methods=['GET'])
@admin_required
def get_reports_route(current_teacher):
    try:
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        
        reports_data = ModerationService.get_reports(status=status, page=page)
        return jsonify({"success": True, **reports_data}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@moderation_bp.route('/admin/reports/<int:report_id>/action', methods=['POST'])
@admin_required
def take_report_action_route(current_teacher, report_id):
    try:
        data = request.get_json()
        action = data.get('action') # 'hide', 'dismiss'

        if action not in ['hide', 'dismiss']:
            return jsonify({"success": False, "error": "Invalid action"}), 400

        report = ModerationService.perform_action(report_id, action)
        return jsonify({
            "success": True, 
            "message": f"Action '{action}' performed successfully.",
            "report": report.to_dict()
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
