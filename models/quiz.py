from . import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    quiz_id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    time_limit = db.Column(db.Integer, nullable=True) # In minutes
    access_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    teacher = db.relationship('Teacher', backref='quizzes')

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    question_id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.quiz_id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), nullable=False) # 'multiple_choice', 'true_false', 'short_answer'
    options = db.Column(JSONB, nullable=True) # For multiple choice
    correct_answer = db.Column(db.Text, nullable=True) # Stored for auto-grading
    points = db.Column(db.Integer, default=1, nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)

    quiz = db.relationship('Quiz', backref=db.backref('questions', cascade="all, delete-orphan", order_by=order))

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    attempt_id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.quiz_id'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    score = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='in_progress', nullable=False) # 'in_progress', 'completed'

    quiz = db.relationship('Quiz', backref=db.backref('attempts', cascade="all, delete-orphan"))

class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answers'
    answer_id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.attempt_id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_questions.question_id'), nullable=False)
    student_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True) # Null for short answers until graded
    points_awarded = db.Column(db.Float, default=0.0, nullable=False)

    attempt = db.relationship('QuizAttempt', backref=db.backref('answers', cascade="all, delete-orphan"))
    question = db.relationship('QuizQuestion')
