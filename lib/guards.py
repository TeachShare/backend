from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Teacher

def verification_required(fn):
    @wraps(fn)
    @jwt_required() 
    def decorated_function(*args, **kwargs):
        teacher_id = get_jwt_identity()
        teacher = Teacher.query.get(teacher_id)

        if not teacher:
            return jsonify({"error": "User not found"}), 404
        
        if not teacher.is_verified:
            return jsonify({
                "error": "Account unverified",
                "message": "Please verify your email to access this features.",
                "verified": False,
            }), 403
        
   
        return fn(teacher, *args, **kwargs)
    
    return decorated_function