from flask import Blueprint, jsonify, request
from services.message_service import MessageService
from services.file_service import AppwriteService
from lib.guards import verification_required

message_bp = Blueprint('message_controller', __name__)
appwrite_service = AppwriteService()

@message_bp.route('/upload', methods=['POST'])
@verification_required
def upload_file(current_teacher):
    try:
        if 'file' not in request.files:
            return jsonify({"error": True, "message": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": True, "message": "No selected file"}), 400

        # Check file size (5MB limit)
        file.seek(0, 2)  # Seek to end of file
        file_size = file.tell()  # Get current position (size)
        file.seek(0)  # Reset to beginning

        if file_size > 5 * 1024 * 1024:
            return jsonify({"error": True, "message": "File size exceeds 5MB limit"}), 400

        upload_result = appwrite_service.upload_file(file)
        return jsonify({"success": True, "data": upload_result}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

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
