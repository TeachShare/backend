from flask import Blueprint, jsonify, request
from services.message_service import MessageService
from lib.guards import verification_required

message_bp = Blueprint('message_controller', __name__)

@message_bp.route('/conversations', methods=['GET'])
@verification_required
def get_conversations(current_teacher):
    try:
        conversations = MessageService.get_conversations(current_teacher.teacher_id)
        return jsonify({"success": True, "data": conversations}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@message_bp.route('/thread/<int:partner_id>', methods=['GET'])
@verification_required
def get_thread(current_teacher, partner_id):
    try:
        messages = MessageService.get_messages(current_teacher.teacher_id, partner_id)
        return jsonify({"success": True, "data": messages}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500
