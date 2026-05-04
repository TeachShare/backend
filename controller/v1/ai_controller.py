from flask import Blueprint, request, jsonify
from services.ai_service import AIService
from services.pdf_service import PDFService
from services.file_service import AppwriteService
from lib.guards import verification_required
from models import db, AIGeneratedContent
import datetime

ai_bp = Blueprint('ai_controller', __name__)
ai_service = AIService()
pdf_service = PDFService()
appwrite_service = AppwriteService()

@ai_bp.route('/generate', methods=['POST'])
@verification_required
def generate_content(current_teacher):
    try:
        data = request.json
        content_type = data.get('type')
        subject = data.get('subject')
        grade = data.get('grade')
        objectives = data.get('objectives')

        if not all([content_type, subject, grade, objectives]):
            return jsonify({"error": True, "message": "Missing required fields"}), 400

        # 1. Generate Content with AI
        result_text = ai_service.generate_content(content_type, subject, grade, objectives)
        title = f"{content_type.capitalize()} - {subject} ({grade})"

        # 2. Generate PDF
        pdf_bytes = pdf_service.create_content_pdf(title, result_text)
        
        # 3. Upload to Appwrite
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ai_gen_{content_type}_{current_teacher.teacher_id}_{timestamp}.pdf"
        upload_res = appwrite_service.upload_bytes(pdf_bytes, filename, "application/pdf")
        pdf_url = upload_res['url']

        # 4. Save to Database
        new_content = AIGeneratedContent(
            teacher_id=current_teacher.teacher_id,
            title=title,
            content_type=content_type,
            content_text=result_text,
            pdf_url=pdf_url,
            subject=subject,
            grade_level=grade
        )
        db.session.add(new_content)
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "data": new_content.to_dict()
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": True, "message": str(e)}), 500

@ai_bp.route('/history', methods=['GET'])
@verification_required
def get_history(current_teacher):
    try:
        history = AIGeneratedContent.query.filter_by(teacher_id=current_teacher.teacher_id).order_by(AIGeneratedContent.created_at.desc()).all()
        return jsonify({
            "success": True,
            "data": [item.to_dict() for item in history]
        }), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

@ai_bp.route('/content/<int:content_id>', methods=['DELETE'])
@verification_required
def delete_content(current_teacher, content_id):
    try:
        content = AIGeneratedContent.query.filter_by(id=content_id, teacher_id=current_teacher.teacher_id).first()
        if not content:
            return jsonify({"error": True, "message": "Content not found"}), 404
        
        db.session.delete(content)
        db.session.commit()
        return jsonify({"success": True, "message": "Content deleted"}), 200
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500
