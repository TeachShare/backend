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
        
        if teacher.is_suspended:
            return jsonify({
                "error": "Account Suspended",
                "message": "This account has been suspended by an administrator for violating community standards.",
                "suspended": True,
            }), 403
        
        # Check if archived - Allow only to /restore endpoint
        from flask import request
        if teacher.is_archived and request.path != '/api/v1/teachers/restore':
            return jsonify({
                "error": "Account Archived",
                "message": "Your account is currently archived. Restore it to access all features.",
                "archived": True,
            }), 403
        
   
        return fn(teacher, *args, **kwargs)
    
    return decorated_function

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        teacher_id = get_jwt_identity()
        teacher = Teacher.query.get(teacher_id)

        if not teacher:
            return jsonify({"error": "User not found"}), 404
        
        if not teacher.is_admin:
            return jsonify({
                "error": "Access Denied",
                "message": "Administrator privileges required."
            }), 403
        
        return fn(teacher, *args, **kwargs)
    
    return decorated_function