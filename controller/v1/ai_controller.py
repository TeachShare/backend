from flask import Blueprint, request, jsonify
from services.ai_service import AIService
from services.pdf_service import PDFService
from services.file_service import AppwriteService
from services.text_extraction_service import TextExtractionService
from lib.guards import verification_required
from models import db, AIGeneratedContent, Subject, GradeLevel, ContentType
import datetime
import os

ai_bp = Blueprint('ai_controller', __name__)
ai_service = AIService()
pdf_service = PDFService()
appwrite_service = AppwriteService()

@ai_bp.route('/analyze-document', methods=['POST'])
@verification_required
def analyze_document(current_teacher):
    try:
        files = request.files.getlist('files')
        
        # Backward compatibility for single 'file' key
        if not files and 'file' in request.files:
            files = [request.files['file']]

        if not files:
            print("DEBUG: 400 Error - No files found in request.files")
            return jsonify({"error": True, "message": "No files uploaded"}), 400
        
        MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
        files_content = []
        
        print(f"DEBUG: Processing {len(files)} uploaded files...")
        for file in files:
            if file.filename == '':
                print("DEBUG: Skipping file with empty filename")
                continue

            # 1. Check File Size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0) # Reset pointer
            print(f"DEBUG: File '{file.filename}' size: {file_size} bytes")

            if file_size > MAX_FILE_SIZE:
                print(f"DEBUG: 400 Error - File '{file.filename}' exceeds limit")
                return jsonify({
                    "error": True, 
                    "message": f"File '{file.filename}' exceeds the 10MB limit. Please upload smaller documents."
                }), 400

            # 2. Extract Text
            file_bytes = file.read()
            text = TextExtractionService.extract_text(file_bytes, file.filename)
            
            if text:
                print(f"DEBUG: Extracted {len(text)} characters from '{file.filename}'")
                files_content.append({
                    "filename": file.filename,
                    "text": text
                })
            else:
                print(f"DEBUG: Failed to extract text from '{file.filename}'")

        if not files_content:
            print("DEBUG: 400 Error - No text extracted from any file")
            return jsonify({"error": True, "message": "Could not extract text from the provided files."}), 400

        # 3. Fetch Reference Metadata for AI context
        subjects = [s.subject_name for s in Subject.query.all()]
        grades = [g.grade_name for g in GradeLevel.query.all()]
        types = [t.type_name for t in ContentType.query.all()]

        # 4. Analyze with AI
        print(f"DEBUG: Starting AI analysis for {len(files_content)} files...")
        metadata = ai_service.analyze_document_metadata(
            files_content, 
            valid_subjects=subjects, 
            valid_grades=grades, 
            valid_types=types
        )
        
        if not metadata:
            print("DEBUG: AI service returned None for metadata")
            return jsonify({"error": True, "message": "AI failed to analyze document"}), 500
            
        print("DEBUG: AI analysis successful")
        return jsonify({
            "success": True,
            "data": metadata
        }), 200
        
    except Exception as e:
        import traceback
        print(f"Analyze Document Route Error: {e}")
        traceback.print_exc()
        return jsonify({"error": True, "message": str(e)}), 500

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
