import secrets
from flask import Blueprint, request, jsonify
from models import db, Quiz, QuizQuestion, QuizAttempt, QuizAnswer, Teacher
from lib.guards import verification_required
from sqlalchemy.orm import joinedload
from services.ai_service import AIService

quiz_bp = Blueprint('quiz_controller', __name__)
ai_service = AIService()

from datetime import datetime, timezone

# --- PUBLIC ROUTES FOR STUDENTS ---

@quiz_bp.route('/public/<access_code>', methods=['GET'])
def get_public_quiz(access_code):
    try:
        quiz = Quiz.query.filter_by(access_code=access_code, is_active=True).first()
        if not quiz:
            return jsonify({"success": False, "message": "Quiz not found or inactive"}), 404
            
        return jsonify({
            "success": True,
            "data": {
                "title": quiz.title,
                "description": quiz.description,
                "time_limit": quiz.time_limit,
                "questions": [{
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "options": q.options,
                    "points": q.points
                } for q in quiz.questions]
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@quiz_bp.route('/public/<access_code>/submit', methods=['POST'])
def submit_quiz_attempt(access_code):
    try:
        quiz = Quiz.query.filter_by(access_code=access_code, is_active=True).first()
        if not quiz:
            return jsonify({"success": False, "message": "Quiz not found or inactive"}), 404
            
        data = request.json
        student_name = data.get('student_name')
        answers = data.get('answers', []) # List of {question_id, student_answer}

        if not student_name:
            return jsonify({"success": False, "message": "Student name is required"}), 400

        # Create Attempt
        new_attempt = QuizAttempt(
            quiz_id=quiz.quiz_id,
            student_name=student_name,
            status='completed',
            completed_at=datetime.now(timezone.utc)
        )
        db.session.add(new_attempt)
        db.session.flush()

        total_score = 0.0
        
        for ans_data in answers:
            q_id = ans_data.get('question_id')
            student_ans = ans_data.get('student_answer')
            
            question = QuizQuestion.query.get(q_id)
            if not question or question.quiz_id != quiz.quiz_id:
                continue
                
            is_correct = None
            points_awarded = 0.0
            
            if question.question_type in ['multiple_choice', 'true_false']:
                is_correct = str(student_ans).strip().lower() == str(question.correct_answer).strip().lower()
                if is_correct:
                    points_awarded = float(question.points)
                    total_score += points_awarded
            
            new_answer = QuizAnswer(
                attempt_id=new_attempt.attempt_id,
                question_id=q_id,
                student_answer=student_ans,
                is_correct=is_correct,
                points_awarded=points_awarded
            )
            db.session.add(new_answer)

        new_attempt.score = total_score
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Quiz submitted successfully",
            "score": total_score,
            "total_points": sum(q.points for q in quiz.questions)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# --- TEACHER ROUTES (PROTECTED) ---

@quiz_bp.route('/generate', methods=['POST'])
@verification_required
def generate_quiz(current_teacher):
    try:
        data = request.json
        topic = data.get('topic')
        grade = data.get('grade')
        num_questions = data.get('num_questions', 5)
        question_types = data.get('question_types', ['multiple_choice'])

        if not all([topic, grade]):
            return jsonify({"success": False, "message": "Missing topic or grade"}), 400

        quiz_json = ai_service.generate_quiz_json(topic, grade, num_questions, question_types)
        
        if not quiz_json:
            return jsonify({"success": False, "message": "AI failed to generate quiz"}), 500
            
        return jsonify({
            "success": True,
            "data": quiz_json
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@quiz_bp.route('/save', methods=['POST'])
@verification_required
def save_quiz(current_teacher):
    try:
        data = request.json
        title = data.get('title')
        description = data.get('description')
        time_limit = data.get('time_limit')
        questions_data = data.get('questions', [])

        if not title or not questions_data:
            return jsonify({"success": False, "message": "Missing title or questions"}), 400

        # Create Quiz
        access_code = secrets.token_urlsafe(8)
        new_quiz = Quiz(
            teacher_id=current_teacher.teacher_id,
            title=title,
            description=description,
            time_limit=time_limit,
            access_code=access_code
        )
        db.session.add(new_quiz)
        db.session.flush()

        # Create Questions
        for i, q_data in enumerate(questions_data):
            new_question = QuizQuestion(
                quiz_id=new_quiz.quiz_id,
                question_text=q_data.get('text'),
                question_type=q_data.get('type'),
                options=q_data.get('options'),
                correct_answer=q_data.get('correct_answer'),
                points=q_data.get('points', 1),
                order=i
            )
            db.session.add(new_question)

        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Quiz saved successfully",
            "quiz_id": new_quiz.quiz_id,
            "access_code": access_code
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@quiz_bp.route('/my-quizzes', methods=['GET'])
@verification_required
def get_my_quizzes(current_teacher):
    try:
        quizzes = Quiz.query.filter_by(teacher_id=current_teacher.teacher_id).order_by(Quiz.created_at.desc()).all()
        return jsonify({
            "success": True,
            "data": [{
                "quiz_id": q.quiz_id,
                "title": q.title,
                "description": q.description,
                "time_limit": q.time_limit,
                "access_code": q.access_code,
                "is_active": q.is_active,
                "created_at": q.created_at.isoformat(),
                "question_count": len(q.questions)
            } for q in quizzes]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@quiz_bp.route('/<int:quiz_id>', methods=['GET'])
@verification_required
def get_quiz_details(current_teacher, quiz_id):
    try:
        quiz = Quiz.query.filter_by(quiz_id=quiz_id, teacher_id=current_teacher.teacher_id).first()
        if not quiz:
            return jsonify({"success": False, "message": "Quiz not found"}), 404
            
        return jsonify({
            "success": True,
            "data": {
                "quiz_id": quiz.quiz_id,
                "title": quiz.title,
                "description": quiz.description,
                "time_limit": quiz.time_limit,
                "access_code": quiz.access_code,
                "is_active": quiz.is_active,
                "questions": [{
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "options": q.options,
                    "correct_answer": q.correct_answer,
                    "points": q.points,
                    "order": q.order
                } for q in quiz.questions]
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@quiz_bp.route('/<int:quiz_id>', methods=['DELETE'])
@verification_required
def delete_quiz(current_teacher, quiz_id):
    try:
        quiz = Quiz.query.filter_by(quiz_id=quiz_id, teacher_id=current_teacher.teacher_id).first()
        if not quiz:
            return jsonify({"success": False, "message": "Quiz not found"}), 404
            
        db.session.delete(quiz)
        db.session.commit()
        return jsonify({"success": True, "message": "Quiz deleted successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@quiz_bp.route('/<int:quiz_id>/attempts', methods=['GET'])
@verification_required
def get_quiz_attempts(current_teacher, quiz_id):
    try:
        quiz = Quiz.query.filter_by(quiz_id=quiz_id, teacher_id=current_teacher.teacher_id).first()
        if not quiz:
            return jsonify({"success": False, "message": "Quiz not found"}), 404
            
        attempts = QuizAttempt.query.filter_by(quiz_id=quiz_id).order_by(QuizAttempt.completed_at.desc()).all()
        
        return jsonify({
            "success": True,
            "data": [{
                "attempt_id": a.attempt_id,
                "student_name": a.student_name,
                "score": a.score,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "status": a.status,
                "total_points": sum(q.points for q in quiz.questions)
            } for a in attempts]
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
